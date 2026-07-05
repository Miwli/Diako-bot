#!/bin/bash

# ─────────────────────────────────────────────
#  Diako Bot — Server Management
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
#  Helper Functions
# ─────────────────────────────────────────────

check_root() {
  if [ "$EUID" -ne 0 ]; then
    print_err "Please run with root privileges: sudo bash install.sh"
    exit 1
  fi
}

get_domain() {
  if [ -f "$ENV_FILE" ]; then
    grep ^DOMAIN= "$ENV_FILE" | cut -d= -f2
  fi
}

get_panel_port() {
  if [ -f "$ENV_FILE" ]; then
    grep ^PANEL_PORT= "$ENV_FILE" | cut -d= -f2
  fi
}

is_installed() {
  [ -d "$INSTALL_DIR" ] && [ -f "$ENV_FILE" ]
}

press_enter() {
  echo ""
  read -rp "  Press Enter to return to menu..."
}

setup_global_command() {
  chmod +x "$INSTALL_DIR/install.sh" 2>/dev/null
  ln -sf "$INSTALL_DIR/install.sh" /usr/local/bin/diako
  print_ok "Global command ready — type 'diako' anywhere to open this menu"
}

# Updates DOMAIN in .env + Nginx config + restarts the panel container.
# Does not touch SSL — do_ssl() calls this then issues/renews the certificate.
apply_domain() {
  local NEW_DOMAIN="$1"
  local PANEL_PORT
  PANEL_PORT=$(get_panel_port)

  sed -i "s/^DOMAIN=.*/DOMAIN=${NEW_DOMAIN}/" "$ENV_FILE"
  sed -i "s/^DJANGO_ALLOWED_HOSTS=.*/DJANGO_ALLOWED_HOSTS=${NEW_DOMAIN}/" "$ENV_FILE"

  cat > /etc/nginx/sites-available/diako-panel <<EOF
server {
    listen 80;
    server_name ${NEW_DOMAIN};
    location / {
        proxy_pass         http://127.0.0.1:${PANEL_PORT};
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }
    # استاتیک‌ها توسط WhiteNoise از طریق خود پنل سرو می‌شوند (proxy_pass بالا)
}
EOF
  nginx -t && systemctl reload nginx

  cd "$INSTALL_DIR"
  docker compose restart panel
}

# ─────────────────────────────────────────────
#  Main Menu
# ─────────────────────────────────────────────

show_menu() {
  clear
  echo -e "${BLUE}${BOLD}"
  echo "  ╔══════════════════════════════════════╗"
  echo "  ║         🤖  Diako Bot Manager        ║"
  echo "  ╚══════════════════════════════════════╝"
  echo -e "${NC}"

  # Service status
  if is_installed; then
    cd "$INSTALL_DIR"
    BOT_STATUS=$(docker compose ps bot --format "{{.Status}}" 2>/dev/null | head -1)
    PANEL_STATUS=$(docker compose ps panel --format "{{.Status}}" 2>/dev/null | head -1)

    if echo "$BOT_STATUS" | grep -q "Up"; then
      echo -e "  Bot:   ${GREEN}● Active${NC}"
    else
      echo -e "  Bot:   ${RED}● Inactive${NC}"
    fi

    if echo "$PANEL_STATUS" | grep -q "Up"; then
      DOMAIN=$(get_domain)
      PANEL_PORT=$(get_panel_port)
      echo -e "  Panel: ${GREEN}● Active${NC}  —  https://${DOMAIN}:${PANEL_PORT}"
    else
      echo -e "  Panel: ${RED}● Inactive${NC}"
    fi
  else
    echo -e "  Status: ${YELLOW}● Not Installed${NC}"
  fi

  echo ""
  echo -e "  ${BOLD}─────────────────────────────────────${NC}"
  echo -e "  ${CYAN}1)${NC}  Full Installation"
  echo -e "  ${CYAN}2)${NC}  Update (pull + rebuild)"
  echo -e "  ${CYAN}3)${NC}  Restart Services"
  echo -e "  ${CYAN}4)${NC}  Container Status"
  echo -e "  ${CYAN}5)${NC}  Bot Logs"
  echo -e "  ${CYAN}6)${NC}  Panel Logs"
  echo -e "  ${CYAN}7)${NC}  Get/Renew SSL"
  echo -e "  ${CYAN}8)${NC}  Edit Settings (.env)"
  echo -e "  ${CYAN}a)${NC}  Change Panel Port"
  echo -e "  ${CYAN}b)${NC}  Create Admin User"
  echo -e "  ${CYAN}c)${NC}  Change Domain"
  echo -e "  ${CYAN}d)${NC}  Backup Database"
  echo -e "  ${CYAN}e)${NC}  Restore Database"
  echo -e "  ${RED}9)${NC}  Full Uninstall"
  echo -e "  ${BOLD}─────────────────────────────────────${NC}"
  echo -e "  ${CYAN}0)${NC}  Exit"
  echo ""
  read -rp "  Select: " CHOICE
}

# ─────────────────────────────────────────────
#  Operations
# ─────────────────────────────────────────────

do_install() {
  check_root

  if is_installed; then
    print_warn "Project is already installed. Choose option 2 for update."
    press_enter; return
  fi

  # Prerequisites
  print_step "Installing prerequisites..."
  apt-get update -qq
  apt-get install -y -qq git curl nginx certbot python3-certbot-nginx 2>&1 | grep -v "is the author" || true
  print_ok "Prerequisites installed"

  # Docker
  print_step "Checking Docker..."
  if ! command -v docker &>/dev/null; then
    print_warn "Docker not found, installing..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
    print_ok "Docker installed"
  else
    print_ok "Docker already installed"
  fi
  if ! docker compose version &>/dev/null; then
    apt-get install -y docker-compose-plugin 2>/dev/null || \
      { print_err "Failed to install Docker Compose."; press_enter; return; }
  fi

  # Clone
  print_step "Cloning code from GitHub..."
  git clone "$REPO_URL" "$INSTALL_DIR" || { print_err "git clone failed — check repo URL and internet."; press_enter; return; }
  # chmod +x on install.sh later (setup_global_command) would otherwise show up
  # as a dirty file to git and block future `git pull` in do_update
  git -C "$INSTALL_DIR" config core.fileMode false
  print_ok "Source code ready"

  # Docker files
  print_step "Downloading Docker files..."
  for f in Dockerfile.bot Dockerfile.panel docker-compose.yml install.sh; do
    curl -fsSL "$RAW_URL/$f" -o "$INSTALL_DIR/$f" || { print_err "Failed to download: $f"; press_enter; return; }
    print_ok "Downloaded: $f"
  done

  # Settings
  print_step "Configuring environment variables..."
  echo ""
  read -rp "  Telegram Bot Token: " BOT_TOKEN
  read -rp "  Admin ID (Enter for auto-generate): " ADMIN_ID
  read -rp "  Panel Domain (e.g., panel.example.com): " DOMAIN
  read -rp "  Panel Port (Enter for 8000): " PANEL_PORT
  read -rp "  Email for SSL: " SSL_EMAIL
  read -rp "  Django Secret Key (Enter for auto-generate): " DJANGO_SECRET
  if [ -z "$DJANGO_SECRET" ]; then
    DJANGO_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || \
                    cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 50)
  fi

  # Default values
  if [ -z "$PANEL_PORT" ]; then
    PANEL_PORT="8000"
  fi

  # If ADMIN_ID is empty, use a default placeholder (user can edit later)
  if [ -z "$ADMIN_ID" ]; then
    ADMIN_ID="123456789"
    print_warn "ADMIN_ID is empty, default value set. Please edit later."
  fi

  cat > "$ENV_FILE" <<EOF
BOT_TOKEN=${BOT_TOKEN}
ADMIN_IDS=${ADMIN_ID}
DJANGO_SECRET_KEY=${DJANGO_SECRET}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${DOMAIN}
PANEL_PORT=${PANEL_PORT}
DOMAIN=${DOMAIN}
SSL_EMAIL=${SSL_EMAIL}
DB_PATH=/shared-data/bot.db
EOF
  chmod 600 "$ENV_FILE"
  print_ok "Environment file created"

  # Copy .env for bot
  cp "$ENV_FILE" "$INSTALL_DIR/bot/.env"
  print_ok "Bot .env file copied"

  # Nginx
  print_step "Configuring Nginx..."
  cat > /etc/nginx/sites-available/diako-panel <<EOF
server {
    listen 80;
    server_name ${DOMAIN};
    location / {
        proxy_pass         http://127.0.0.1:${PANEL_PORT};
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }
    # استاتیک‌ها توسط WhiteNoise از طریق خود پنل سرو می‌شوند (proxy_pass بالا)
}
EOF
  ln -sf /etc/nginx/sites-available/diako-panel /etc/nginx/sites-enabled/diako-panel
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable nginx
  systemctl start nginx || systemctl reload nginx
  print_ok "Nginx configured"

  # Build
  print_step "Building and starting containers..."
  cd "$INSTALL_DIR"
  docker compose build --no-cache
  docker compose up -d
  print_ok "Containers started"

  # Global command
  setup_global_command

  # SSL
  do_ssl

  press_enter
}

do_update() {
  check_root
  if ! is_installed; then
    print_err "Project not installed. Choose option 1 first."
    press_enter; return
  fi

  print_step "Updating code from GitHub..."
  # self-heal old installs where chmod +x on install.sh (setup_global_command)
  # left a dirty file-mode diff that would otherwise block this pull
  git -C "$INSTALL_DIR" config core.fileMode false
  if ! git -C "$INSTALL_DIR" pull; then
    print_err "git pull failed — server has local changes or a conflict. Not rebuilding with stale code."
    print_warn "Check manually: cd $INSTALL_DIR && git status"
    press_enter; return
  fi
  print_ok "Code updated"

  print_step "Downloading Docker files..."
  for f in Dockerfile.bot Dockerfile.panel docker-compose.yml; do
    curl -fsSL "$RAW_URL/$f" -o "$INSTALL_DIR/$f"
    print_ok "Updated: $f"
  done

  print_step "Rebuilding containers..."
  cd "$INSTALL_DIR"
  docker compose down
  docker compose build
  docker compose up -d
  print_ok "Update complete"

  setup_global_command

  press_enter
}

do_restart() {
  check_root
  if ! is_installed; then
    print_err "Project not installed."
    press_enter; return
  fi
  print_step "Restarting services..."
  cd "$INSTALL_DIR"
  docker compose restart
  print_ok "Restarted"
  press_enter
}

do_status() {
  if ! is_installed; then
    print_err "Project not installed."
    press_enter; return
  fi
  echo ""
  cd "$INSTALL_DIR"
  docker compose ps
  press_enter
}

do_logs_bot() {
  if ! is_installed; then
    print_err "Project not installed."
    press_enter; return
  fi
  echo -e "\n${YELLOW}Ctrl+C to exit log${NC}\n"
  cd "$INSTALL_DIR"
  docker compose logs -f bot
}

do_logs_panel() {
  if ! is_installed; then
    print_err "Project not installed."
    press_enter; return
  fi
  echo -e "\n${YELLOW}Ctrl+C to exit log${NC}\n"
  cd "$INSTALL_DIR"
  docker compose logs -f panel
}

do_change_domain() {
  check_root
  if ! is_installed; then
    print_err "Project not installed."
    press_enter; return
  fi

  CURRENT_DOMAIN=$(get_domain)
  echo ""
  echo -e "  Current domain: ${CYAN}${CURRENT_DOMAIN}${NC}"
  read -rp "  New domain: " NEW_DOMAIN

  if [ -z "$NEW_DOMAIN" ] || [ "$NEW_DOMAIN" = "$CURRENT_DOMAIN" ]; then
    print_warn "No change. Cancelled."
    press_enter; return
  fi

  apply_domain "$NEW_DOMAIN"
  print_ok "Domain changed to ${NEW_DOMAIN}"
  print_warn "If you use SSL, run option 7 to issue/renew the certificate for the new domain."
  press_enter
}

do_ssl() {
  check_root
  if ! is_installed; then
    print_err "Project not installed."
    press_enter; return
  fi

  DOMAIN=$(get_domain)
  SSL_EMAIL=$(grep ^SSL_EMAIL= "$ENV_FILE" 2>/dev/null | cut -d= -f2)

  if [ -z "$DOMAIN" ] || [ -z "$SSL_EMAIL" ]; then
    print_err "Domain or email not found in .env."
    press_enter; return
  fi

  echo ""
  echo -e "  Domain: ${CYAN}${DOMAIN}${NC}"

  print_step "Getting SSL certificate for $DOMAIN"
  echo -e "${YELLOW}⚠ Make sure DNS for ${DOMAIN} points to this server's IP!${NC}"
  echo ""
  read -rp "  DNS configured? (y/n): " DNS_READY

  if [ "$DNS_READY" = "y" ] || [ "$DNS_READY" = "Y" ]; then
    # چک می‌کنیم فقط اگر سرویسی غیر از nginx روی پورت ۸۰ باشه (مثل Apache)
    PORT80=$(ss -tlnp | grep ':80 ' | grep -v nginx | awk '{print $NF}' | head -1)
    if [ -n "$PORT80" ]; then
      print_err "Port 80 is in use by another service: $PORT80"
      print_warn "If Apache: systemctl stop apache2 && systemctl disable apache2"
      print_warn "Free up port 80 then try option 7 again."
      press_enter; return
    fi

    if certbot --nginx -d "$DOMAIN" --email "$SSL_EMAIL" --agree-tos --non-interactive --redirect; then
      print_ok "SSL certificate obtained ✓"
      (crontab -l 2>/dev/null | grep -v certbot; echo "0 3 * * * certbot renew --quiet && systemctl reload nginx") | crontab -
      print_ok "SSL auto-renewal configured"
    else
      print_err "SSL failed — log: /var/log/letsencrypt/letsencrypt.log"
      print_warn "Fix the issue then try option 7 again."
    fi
  else
    print_warn "Cancelled. Run this option again when DNS is ready."
  fi

  press_enter
}

do_edit_env() {
  if ! is_installed; then
    print_err "Project not installed."
    press_enter; return
  fi
  nano "$ENV_FILE"
  echo ""
  read -rp "  Restart services to apply changes? (y/n): " DO_RESTART
  if [ "$DO_RESTART" = "y" ] || [ "$DO_RESTART" = "Y" ]; then
    cd "$INSTALL_DIR"
    docker compose restart
    print_ok "Restarted"
  fi
  press_enter
}

do_uninstall() {
  check_root
  echo ""
  echo -e "${RED}${BOLD}⚠ This will delete everything!${NC}"
  echo -e "  Includes: code, database, settings, containers"
  echo ""
  read -rp "  Confirm? Type DELETE: " CONFIRM

  if [ "$CONFIRM" = "DELETE" ]; then
    print_step "Removing containers..."
    cd "$INSTALL_DIR" 2>/dev/null && docker compose down --volumes 2>/dev/null || true

    print_step "Removing files..."
    rm -rf "$INSTALL_DIR"

    print_step "Removing Nginx config..."
    rm -f /etc/nginx/sites-enabled/diako-panel
    rm -f /etc/nginx/sites-available/diako-panel
    systemctl reload nginx 2>/dev/null || true

    print_ok "Everything removed"
  else
    print_warn "Cancelled"
  fi

  press_enter
}

do_change_port() {
  check_root
  if ! is_installed; then
    print_err "Project not installed."
    press_enter; return
  fi

  CURRENT_PORT=$(get_panel_port)
  echo ""
  echo -e "  Current port: ${CYAN}${CURRENT_PORT}${NC}"
  read -rp "  New port: " NEW_PORT

  if [ -z "$NEW_PORT" ]; then
    print_warn "No port entered. Cancelled."
    press_enter; return
  fi

  # Update .env
  sed -i "s/^PANEL_PORT=.*/PANEL_PORT=${NEW_PORT}/" "$ENV_FILE"
  print_ok ".env updated"

  # Update Nginx config
  DOMAIN=$(get_domain)
  cat > /etc/nginx/sites-available/diako-panel <<EOF
server {
    listen 80;
    server_name ${DOMAIN};
    location / {
        proxy_pass         http://127.0.0.1:${NEW_PORT};
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }
    # استاتیک‌ها توسط WhiteNoise از طریق خود پنل سرو می‌شوند (proxy_pass بالا)
}
EOF
  nginx -t && systemctl reload nginx
  print_ok "Nginx updated"

  # Restart containers
  print_step "Restarting containers..."
  cd "$INSTALL_DIR"
  docker compose down
  docker compose up -d
  print_ok "Port changed to ${NEW_PORT} ✓"

  press_enter
}

do_create_admin() {
  if ! is_installed; then
    print_err "Project not installed."
    press_enter; return
  fi

  # Check panel is running
  PANEL_STATUS=$(docker compose -f "$INSTALL_DIR/docker-compose.yml" ps panel --format "{{.Status}}" 2>/dev/null | head -1)
  if ! echo "$PANEL_STATUS" | grep -q "Up"; then
    print_err "Panel container is not running."
    press_enter; return
  fi

  echo ""
  read -rp "  Username: " ADMIN_USER
  read -rp "  Email: " ADMIN_EMAIL
  read -rsp "  Password: " ADMIN_PASS
  echo ""

  if [ -z "$ADMIN_USER" ] || [ -z "$ADMIN_PASS" ]; then
    print_err "Username and password cannot be empty."
    press_enter; return
  fi

  docker exec diako-panel python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if User.objects.filter(username='${ADMIN_USER}').exists():
    print('ERROR: Username already exists')
else:
    User.objects.create_superuser('${ADMIN_USER}', '${ADMIN_EMAIL}', '${ADMIN_PASS}')
    print('SUCCESS')
" | grep -q "SUCCESS" && print_ok "Admin user '${ADMIN_USER}' created ✓" || print_err "Failed — username may already exist."

  press_enter
}

do_backup() {
  if ! is_installed; then
    print_err "Project not installed."
    press_enter; return
  fi

  DB_FILE="$INSTALL_DIR/shared-data/bot.db"
  if [ ! -f "$DB_FILE" ]; then
    print_err "Database file not found: $DB_FILE"
    press_enter; return
  fi

  mkdir -p "$INSTALL_DIR/backups"
  STAMP=$(date +%Y%m%d_%H%M%S)
  DEST="$INSTALL_DIR/backups/bot_${STAMP}.db.gz"

  print_step "Backing up database..."
  gzip -c "$DB_FILE" > "$DEST"
  print_ok "Backup saved: $DEST"

  press_enter
}

do_restore() {
  check_root
  if ! is_installed; then
    print_err "Project not installed."
    press_enter; return
  fi

  BACKUP_DIR="$INSTALL_DIR/backups"
  if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
    print_err "No backups found in $BACKUP_DIR"
    press_enter; return
  fi

  echo ""
  echo -e "  ${BOLD}Available backups:${NC}"
  mapfile -t FILES < <(ls -1t "$BACKUP_DIR")
  i=1
  for f in "${FILES[@]}"; do
    echo "  $i) $f"
    i=$((i + 1))
  done

  echo ""
  read -rp "  Select backup number to restore (0 to cancel): " SEL
  if ! [[ "$SEL" =~ ^[0-9]+$ ]] || [ "$SEL" -lt 1 ] || [ "$SEL" -gt "${#FILES[@]}" ]; then
    print_warn "Cancelled."
    press_enter; return
  fi

  CHOSEN="${FILES[$((SEL - 1))]}"
  echo ""
  echo -e "${RED}${BOLD}⚠ This will overwrite the current database with: ${CHOSEN}${NC}"
  read -rp "  Confirm? Type YES: " CONFIRM
  if [ "$CONFIRM" != "YES" ]; then
    print_warn "Cancelled."
    press_enter; return
  fi

  print_step "Stopping services..."
  cd "$INSTALL_DIR"
  docker compose stop bot panel

  print_step "Restoring database..."
  DB_FILE="$INSTALL_DIR/shared-data/bot.db"
  if [[ "$CHOSEN" == *.gz ]]; then
    gunzip -c "$BACKUP_DIR/$CHOSEN" > "$DB_FILE"
  else
    cp "$BACKUP_DIR/$CHOSEN" "$DB_FILE"
  fi
  print_ok "Database restored"

  print_step "Starting services..."
  docker compose up -d
  print_ok "Restore complete ✓"

  press_enter
}

# ─────────────────────────────────────────────
#  Main Loop
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
    8) do_edit_env    ;;
    a) do_change_port ;;
    b) do_create_admin;;
    c) do_change_domain;;
    d) do_backup      ;;
    e) do_restore     ;;
    9) do_uninstall   ;;
    0) clear; echo -e "${GREEN}Goodbye!${NC}\n"; exit 0 ;;
    *) print_warn "Invalid option" ; sleep 1 ;;
  esac
done