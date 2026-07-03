#!/bin/bash
set -e

# ─────────────────────────────────────────────
#  Diako Bot — نصب خودکار
# ─────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_step() { echo -e "\n${CYAN}▶ $1${NC}"; }
print_ok()   { echo -e "${GREEN}✔ $1${NC}"; }
print_warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_err()  { echo -e "${RED}✘ $1${NC}"; exit 1; }

REPO_URL="https://github.com/Miwli/Diako-bot.git"
INSTALL_DIR="/opt/diako-bot"

# ── ۱. بررسی دسترسی root ──────────────────────
if [ "$EUID" -ne 0 ]; then
  print_err "لطفاً با دسترسی root اجرا کنید: sudo bash install.sh"
fi

# ── ۲. نصب پیش‌نیازها ────────────────────────
print_step "نصب پیش‌نیازها..."
apt-get update -qq
apt-get install -y -qq git curl nginx certbot python3-certbot-nginx
print_ok "پیش‌نیازها نصب شدند"

# ── ۳. نصب Docker ────────────────────────────
print_step "بررسی Docker..."
if ! command -v docker &>/dev/null; then
  print_warn "Docker پیدا نشد، در حال نصب..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
  print_ok "Docker نصب شد"
else
  print_ok "Docker از قبل نصب است: $(docker --version)"
fi

if ! docker compose version &>/dev/null; then
  apt-get install -y docker-compose-plugin 2>/dev/null || \
    print_err "نصب Docker Compose ناموفق بود."
fi
print_ok "Docker Compose آماده است"

# ── ۴. دریافت سورس ───────────────────────────
print_step "دریافت کد از GitHub..."
if [ -d "$INSTALL_DIR" ]; then
  print_warn "پوشه $INSTALL_DIR وجود دارد، در حال آپدیت..."
  git -C "$INSTALL_DIR" pull
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
print_ok "سورس کد آماده شد"

# ── ۵. کپی فایل‌های داکر ─────────────────────
print_step "کپی فایل‌های داکر..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for f in Dockerfile.bot Dockerfile.panel docker-compose.yml; do
  if [ -f "$SCRIPT_DIR/$f" ]; then
    cp "$SCRIPT_DIR/$f" "$INSTALL_DIR/$f"
    print_ok "کپی شد: $f"
  fi
done

# ── ۶. تنظیمات محیطی ─────────────────────────
print_step "تنظیم متغیرهای محیطی..."
ENV_FILE="$INSTALL_DIR/.env"

if [ -f "$ENV_FILE" ]; then
  print_warn "فایل .env از قبل وجود دارد. برای ویرایش: nano $ENV_FILE"
  source "$ENV_FILE"
else
  echo ""
  echo -e "${YELLOW}لطفاً اطلاعات زیر را وارد کنید:${NC}"
  echo ""

  read -rp "  توکن ربات تلگرام: " BOT_TOKEN
  read -rp "  آیدی عددی ادمین: " ADMIN_ID
  read -rp "  دامنه پنل (مثال: panel.example.com): " DOMAIN
  read -rp "  ایمیل برای SSL: " SSL_EMAIL
  read -rp "  Secret Key جنگو (Enter برای تولید خودکار): " DJANGO_SECRET
  if [ -z "$DJANGO_SECRET" ]; then
    DJANGO_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || \
                    cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 50)
  fi

  cat > "$ENV_FILE" <<EOF
# ── ربات ────────────────────────
BOT_TOKEN=${BOT_TOKEN}
ADMIN_ID=${ADMIN_ID}

# ── پنل جنگو ────────────────────
DJANGO_SECRET_KEY=${DJANGO_SECRET}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${DOMAIN}
PANEL_PORT=8000

# ── دامنه و SSL ──────────────────
DOMAIN=${DOMAIN}
SSL_EMAIL=${SSL_EMAIL}

# ── دیتابیس ─────────────────────
DB_PATH=/app/db/db.sqlite3
EOF

  chmod 600 "$ENV_FILE"
  print_ok "فایل .env ساخته شد"
fi

# مقادیر را از .env بخوان
DOMAIN=$(grep ^DOMAIN= "$ENV_FILE" | cut -d= -f2)
SSL_EMAIL=$(grep ^SSL_EMAIL= "$ENV_FILE" | cut -d= -f2)

# ── ۷. پیکربندی اولیه Nginx (بدون SSL برای certbot) ──
print_step "پیکربندی Nginx..."
NGINX_CONF="/etc/nginx/sites-available/diako-panel"

cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias /opt/diako-bot/staticfiles/;
    }
}
EOF

ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/diako-panel
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl start nginx || systemctl reload nginx
print_ok "Nginx پیکربندی شد"

# ── ۸. Build و اجرا ──────────────────────────
print_step "ساخت و راه‌اندازی کانتینرها..."
cd "$INSTALL_DIR"
docker compose down --remove-orphans 2>/dev/null || true
docker compose build --no-cache
docker compose up -d
print_ok "کانتینرها راه‌اندازی شدند"

# ── ۹. گرفتن گواهی SSL ───────────────────────
print_step "دریافت گواهی SSL از Let's Encrypt..."
echo -e "${YELLOW}⚠ مطمئن شو که DNS دامنه ${DOMAIN} به IP این سرور اشاره می‌کند!${NC}"
echo ""
read -rp "  آیا DNS ست شده و آماده‌ای؟ (y/n): " DNS_READY

if [ "$DNS_READY" = "y" ] || [ "$DNS_READY" = "Y" ]; then
  certbot --nginx \
    -d "$DOMAIN" \
    --email "$SSL_EMAIL" \
    --agree-tos \
    --non-interactive \
    --redirect
  print_ok "SSL گرفته شد — سایت حالا روی HTTPS فعاله"

  # تمدید خودکار
  (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && systemctl reload nginx") | crontab -
  print_ok "تمدید خودکار SSL تنظیم شد (هر روز ساعت ۳ بامداد)"
else
  print_warn "SSL رد شد. بعداً می‌تونی با این دستور بگیری:"
  echo "  certbot --nginx -d $DOMAIN --email $SSL_EMAIL --agree-tos --non-interactive --redirect"
fi

# ── ۱۰. وضعیت نهایی ──────────────────────────
echo ""
print_step "وضعیت سرویس‌ها:"
docker compose ps

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✔ نصب با موفقیت انجام شد!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  🌐 پنل مدیریت:   https://${DOMAIN}"
echo -e "  📁 مسیر نصب:     $INSTALL_DIR"
echo -e "  📝 تنظیمات:      $ENV_FILE"
echo ""
echo -e "  ${CYAN}دستورات مفید:${NC}"
echo -e "  لاگ ربات:    docker compose -f $INSTALL_DIR/docker-compose.yml logs -f bot"
echo -e "  لاگ پنل:     docker compose -f $INSTALL_DIR/docker-compose.yml logs -f panel"
echo -e "  ریستارت:     docker compose -f $INSTALL_DIR/docker-compose.yml restart"
echo -e "  آپدیت:       bash $INSTALL_DIR/install.sh"
echo -e "  وضعیت SSL:   certbot certificates"
echo ""
