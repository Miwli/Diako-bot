#!/bin/bash

# ─────────────────────────────────────────────
#  Diako Bot — مدیریت سرور
# ─────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

print_step() { echo -e "\n${CYAN}▶ $1${NC}"; }
print_ok()   { echo -e "${GREEN}✔ $1${NC}"; }
print_warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_err()  { echo -e "${RED}✘ $1${NC}"; }

REPO_URL="https://github.com/Miwli/Diako-bot.git"
RAW_URL="https://raw.githubusercontent.com/Miwli/Diako-bot/main"
INSTALL_DIR="/opt/diako-bot"
ENV_FILE="$INSTALL_DIR/.env"

# ─────────────────────────────────────────────
#  توابع کمکی
# ─────────────────────────────────────────────

check_root() {
  if [ "$EUID" -ne 0 ]; then
    print_err "لطفاً با دسترسی root اجرا کنید: sudo bash install.sh"
    exit 1
  fi
}

get_domain() {
  if [ -f "$ENV_FILE" ]; then
    grep ^DOMAIN= "$ENV_FILE" | cut -d= -f2
  fi
}

is_installed() {
  [ -d "$INSTALL_DIR" ] && [ -f "$ENV_FILE" ]
}

press_enter() {
  echo ""
  read -rp "  اینتر بزن تا به منو برگردی..."
}

# ─────────────────────────────────────────────
#  منو اصلی
# ─────────────────────────────────────────────

show_menu() {
  clear
  echo -e "${BLUE}${BOLD}"
  echo "  ╔══════════════════════════════════════╗"
  echo "  ║         🤖  Diako Bot Manager        ║"
  echo "  ╚══════════════════════════════════════╝"
  echo -e "${NC}"

  # وضعیت سرویس‌ها
  if is_installed; then
    cd "$INSTALL_DIR"
    BOT_STATUS=$(docker compose ps bot --format "{{.Status}}" 2>/dev/null | head -1)
    PANEL_STATUS=$(docker compose ps panel --format "{{.Status}}" 2>/dev/null | head -1)

    if echo "$BOT_STATUS" | grep -q "Up"; then
      echo -e "  ربات:   ${GREEN}● فعال${NC}"
    else
      echo -e "  ربات:   ${RED}● غیرفعال${NC}"
    fi

    if echo "$PANEL_STATUS" | grep -q "Up"; then
      DOMAIN=$(get_domain)
      echo -e "  پنل:    ${GREEN}● فعال${NC}  —  https://${DOMAIN}"
    else
      echo -e "  پنل:    ${RED}● غیرفعال${NC}"
    fi
  else
    echo -e "  وضعیت:  ${YELLOW}● نصب نشده${NC}"
  fi

  echo ""
  echo -e "  ${BOLD}─────────────────────────────────────${NC}"
  echo -e "  ${CYAN}1)${NC}  نصب کامل"
  echo -e "  ${CYAN}2)${NC}  آپدیت (pull + rebuild)"
  echo -e "  ${CYAN}3)${NC}  ریستارت سرویس‌ها"
  echo -e "  ${CYAN}4)${NC}  وضعیت کانتینرها"
  echo -e "  ${CYAN}5)${NC}  لاگ ربات"
  echo -e "  ${CYAN}6)${NC}  لاگ پنل"
  echo -e "  ${CYAN}7)${NC}  گرفتن / تمدید SSL"
  echo -e "  ${CYAN}8)${NC}  ویرایش تنظیمات (.env)"
  echo -e "  ${RED}9)${NC}  حذف کامل"
  echo -e "  ${BOLD}─────────────────────────────────────${NC}"
  echo -e "  ${CYAN}0)${NC}  خروج"
  echo ""
  read -rp "  انتخاب کن: " CHOICE
}

# ─────────────────────────────────────────────
#  عملیات‌ها
# ─────────────────────────────────────────────

do_install() {
  check_root

  if is_installed; then
    print_warn "پروژه از قبل نصب است. برای آپدیت گزینه ۲ رو انتخاب کن."
    press_enter; return
  fi

  # پیش‌نیازها
  print_step "نصب پیش‌نیازها..."
  apt-get update -qq
  apt-get install -y -qq git curl nginx certbot python3-certbot-nginx
  print_ok "پیش‌نیازها نصب شدند"

  # Docker
  print_step "بررسی Docker..."
  if ! command -v docker &>/dev/null; then
    print_warn "Docker پیدا نشد، در حال نصب..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
    print_ok "Docker نصب شد"
  else
    print_ok "Docker از قبل نصب است"
  fi
  if ! docker compose version &>/dev/null; then
    apt-get install -y docker-compose-plugin 2>/dev/null || \
      { print_err "نصب Docker Compose ناموفق بود."; press_enter; return; }
  fi

  # Clone
  print_step "دریافت کد از GitHub..."
  git clone "$REPO_URL" "$INSTALL_DIR"
  print_ok "سورس کد آماده شد"

  # فایل‌های داکر
  print_step "دانلود فایل‌های داکر..."
  for f in Dockerfile.bot Dockerfile.panel docker-compose.yml; do
    curl -fsSL "$RAW_URL/$f" -o "$INSTALL_DIR/$f"
    print_ok "دانلود شد: $f"
  done

  # تنظیمات
  print_step "تنظیم متغیرهای محیطی..."
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
BOT_TOKEN=${BOT_TOKEN}
ADMIN_ID=${ADMIN_ID}
DJANGO_SECRET_KEY=${DJANGO_SECRET}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${DOMAIN}
PANEL_PORT=8000
DOMAIN=${DOMAIN}
SSL_EMAIL=${SSL_EMAIL}
DB_PATH=/app/db/db.sqlite3
EOF
  chmod 600 "$ENV_FILE"
  print_ok "فایل .env ساخته شد"

  # Nginx
  print_step "پیکربندی Nginx..."
  cat > /etc/nginx/sites-available/diako-panel <<EOF
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
  ln -sf /etc/nginx/sites-available/diako-panel /etc/nginx/sites-enabled/diako-panel
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable nginx
  systemctl start nginx || systemctl reload nginx
  print_ok "Nginx راه‌اندازی شد"

  # Build
  print_step "ساخت و راه‌اندازی کانتینرها..."
  cd "$INSTALL_DIR"
  docker compose build --no-cache
  docker compose up -d
  print_ok "کانتینرها راه‌اندازی شدند"

  # SSL
  do_ssl

  press_enter
}

do_update() {
  check_root
  if ! is_installed; then
    print_err "پروژه نصب نیست. ابتدا گزینه ۱ رو انتخاب کن."
    press_enter; return
  fi

  print_step "آپدیت کد از GitHub..."
  git -C "$INSTALL_DIR" pull
  print_ok "کد آپدیت شد"

  print_step "دانلود فایل‌های داکر..."
  for f in Dockerfile.bot Dockerfile.panel docker-compose.yml; do
    curl -fsSL "$RAW_URL/$f" -o "$INSTALL_DIR/$f"
    print_ok "آپدیت شد: $f"
  done

  print_step "Rebuild کانتینرها..."
  cd "$INSTALL_DIR"
  docker compose down
  docker compose build --no-cache
  docker compose up -d
  print_ok "آپدیت کامل شد"

  press_enter
}

do_restart() {
  check_root
  if ! is_installed; then
    print_err "پروژه نصب نیست."
    press_enter; return
  fi
  print_step "ریستارت سرویس‌ها..."
  cd "$INSTALL_DIR"
  docker compose restart
  print_ok "ریستارت شد"
  press_enter
}

do_status() {
  if ! is_installed; then
    print_err "پروژه نصب نیست."
    press_enter; return
  fi
  echo ""
  cd "$INSTALL_DIR"
  docker compose ps
  press_enter
}

do_logs_bot() {
  if ! is_installed; then
    print_err "پروژه نصب نیست."
    press_enter; return
  fi
  echo -e "\n${YELLOW}Ctrl+C برای خروج از لاگ${NC}\n"
  cd "$INSTALL_DIR"
  docker compose logs -f bot
}

do_logs_panel() {
  if ! is_installed; then
    print_err "پروژه نصب نیست."
    press_enter; return
  fi
  echo -e "\n${YELLOW}Ctrl+C برای خروج از لاگ${NC}\n"
  cd "$INSTALL_DIR"
  docker compose logs -f panel
}

do_ssl() {
  check_root
  DOMAIN=$(get_domain)
  SSL_EMAIL=$(grep ^SSL_EMAIL= "$ENV_FILE" 2>/dev/null | cut -d= -f2)

  if [ -z "$DOMAIN" ] || [ -z "$SSL_EMAIL" ]; then
    print_err "دامنه یا ایمیل در .env پیدا نشد."
    press_enter; return
  fi

  print_step "دریافت گواهی SSL برای $DOMAIN"
  echo -e "${YELLOW}⚠ مطمئن شو DNS دامنه به IP این سرور اشاره می‌کند!${NC}"
  echo ""
  read -rp "  آیا DNS ست شده؟ (y/n): " DNS_READY

  if [ "$DNS_READY" = "y" ] || [ "$DNS_READY" = "Y" ]; then
    certbot --nginx \
      -d "$DOMAIN" \
      --email "$SSL_EMAIL" \
      --agree-tos \
      --non-interactive \
      --redirect
    print_ok "SSL گرفته شد ✓"
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && systemctl reload nginx") | crontab -
    print_ok "تمدید خودکار SSL تنظیم شد"
  else
    print_warn "لغو شد. هر وقت DNS آماده شد دوباره این گزینه رو بزن."
  fi

  press_enter
}

do_edit_env() {
  if ! is_installed; then
    print_err "پروژه نصب نیست."
    press_enter; return
  fi
  nano "$ENV_FILE"
  echo ""
  read -rp "  ریستارت سرویس‌ها برای اعمال تغییرات؟ (y/n): " DO_RESTART
  if [ "$DO_RESTART" = "y" ] || [ "$DO_RESTART" = "Y" ]; then
    cd "$INSTALL_DIR"
    docker compose restart
    print_ok "ریستارت شد"
  fi
  press_enter
}

do_uninstall() {
  check_root
  echo ""
  echo -e "${RED}${BOLD}⚠ این عملیات همه چیز رو حذف می‌کند!${NC}"
  echo -e "  شامل: کد، دیتابیس، تنظیمات، کانتینرها"
  echo ""
  read -rp "  مطمئنی؟ برای تایید بنویس DELETE: " CONFIRM

  if [ "$CONFIRM" = "DELETE" ]; then
    print_step "حذف کانتینرها..."
    cd "$INSTALL_DIR" 2>/dev/null && docker compose down --volumes 2>/dev/null || true

    print_step "حذف فایل‌ها..."
    rm -rf "$INSTALL_DIR"

    print_step "حذف Nginx config..."
    rm -f /etc/nginx/sites-enabled/diako-panel
    rm -f /etc/nginx/sites-available/diako-panel
    systemctl reload nginx 2>/dev/null || true

    print_ok "همه چیز حذف شد"
  else
    print_warn "لغو شد"
  fi

  press_enter
}

# ─────────────────────────────────────────────
#  حلقه اصلی
# ─────────────────────────────────────────────

while true; do
  show_menu
  case "$CHOICE" in
    1) do_install   ;;
    2) do_update    ;;
    3) do_restart   ;;
    4) do_status    ;;
    5) do_logs_bot  ;;
    6) do_logs_panel;;
    7) do_ssl       ;;
    8) do_edit_env  ;;
    9) do_uninstall ;;
    0) clear; echo -e "${GREEN}خداحافظ!${NC}\n"; exit 0 ;;
    *) print_warn "گزینه نامعتبر" ; sleep 1 ;;
  esac
done
