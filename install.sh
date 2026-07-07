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
INSTANCES_DIR="$INSTALL_DIR/instances"
MANAGER_CONF="$INSTANCES_DIR/.manager.conf"
INSTANCE_COMPOSE="$INSTALL_DIR/docker-compose.instance.yml"

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

# Rewriting the nginx config wipes the 443 block certbot added to it.
# If a cert already exists for the domain, reinstall it so https keeps working.
restore_ssl() {
  local domain="$1"
  [ -d "/etc/letsencrypt/live/${domain}" ] || return 0
  if certbot --nginx -d "$domain" --non-interactive --redirect; then
    print_ok "SSL config restored for ${domain}"
  else
    print_warn "SSL restore failed for ${domain} — run the SSL option again."
  fi
}

# Updates DOMAIN in .env + Nginx config + restarts the panel container.
# New certs are issued elsewhere (do_ssl / main_domain_ssl) — this only
# re-installs an existing one after the config rewrite.
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
  restore_ssl "$NEW_DOMAIN"

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
  echo -e "  ${CYAN}9)${NC}  Change Panel Port"
  echo -e "  ${CYAN}10)${NC} Create Admin User"
  echo -e "  ${CYAN}11)${NC} Change Domain"
  echo -e "  ${CYAN}12)${NC} Backup Database"
  echo -e "  ${CYAN}13)${NC} Restore Database"
  echo -e "  ${CYAN}14)${NC} Reseller Management"
  echo -e "  ${RED}15)${NC} Full Uninstall"
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
  for f in Dockerfile.bot Dockerfile.panel docker-compose.yml docker-compose.instance.yml install.sh; do
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
  for f in Dockerfile.bot Dockerfile.panel docker-compose.yml docker-compose.instance.yml; do
    curl -fsSL "$RAW_URL/$f" -o "$INSTALL_DIR/$f"
    print_ok "Updated: $f"
  done

  print_step "Rebuilding containers..."
  cd "$INSTALL_DIR"
  docker compose down
  docker compose build
  docker compose up -d
  print_ok "Update complete"

  # reseller instances run the same images — recreate them so they pick up the new build
  if [ -d "$INSTANCES_DIR" ]; then
    for slug in $(list_instances); do
      print_step "Updating reseller '${slug}'..."
      icompose "$slug" up -d --force-recreate
      print_ok "Reseller '${slug}' updated"
    done
  fi

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
  main_domain_ssl "$CURRENT_DOMAIN" "$NEW_DOMAIN"
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
  OLD_DOMAIN=$(get_domain)
  nano "$ENV_FILE"
  echo ""
  read -rp "  Apply changes now? (y/n): " DO_APPLY
  if [ "$DO_APPLY" = "y" ] || [ "$DO_APPLY" = "Y" ]; then
    NEW_DOMAIN=$(get_domain)
    # .env is the source of truth — regenerate nginx and recreate containers from it
    apply_domain "$NEW_DOMAIN"
    cd "$INSTALL_DIR"
    docker compose down
    docker compose up -d
    if [ -n "$OLD_DOMAIN" ] && [ "$NEW_DOMAIN" != "$OLD_DOMAIN" ]; then
      main_domain_ssl "$OLD_DOMAIN" "$NEW_DOMAIN"
    fi
    print_ok "All changes applied"
  fi
  press_enter
}

# swaps the ssl cert when the main domain changes — old one out, new one in
main_domain_ssl() {
  local old="$1" new="$2"
  local email
  email=$(grep ^SSL_EMAIL= "$ENV_FILE" 2>/dev/null | cut -d= -f2)
  print_step "Domain changed ${old} → ${new}, updating SSL..."
  certbot delete --cert-name "$old" --non-interactive 2>/dev/null || true
  if certbot --nginx -d "$new" --email "$email" --agree-tos --non-interactive --redirect; then
    print_ok "SSL ready for ${new}"
  else
    print_warn "SSL failed — check DNS, then run option 7."
  fi
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
  restore_ssl "$DOMAIN"
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

  (cd "$INSTALL_DIR" && docker compose exec -T panel python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if User.objects.filter(username='${ADMIN_USER}').exists():
    print('ERROR: Username already exists')
else:
    User.objects.create_superuser('${ADMIN_USER}', '${ADMIN_EMAIL}', '${ADMIN_PASS}')
    print('SUCCESS')
") | grep -q "SUCCESS" && print_ok "Admin user '${ADMIN_USER}' created ✓" || print_err "Failed — username may already exist."

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
#  Reseller Manager
# ─────────────────────────────────────────────

# docker compose wrapper for one instance — keeps project name/paths in one place
icompose() {
  local slug="$1"; shift
  docker compose -p "diako-${slug}" -f "$INSTANCE_COMPOSE" \
    --project-directory "$INSTANCES_DIR/$slug" "$@"
}

get_ienv() {
  grep "^$2=" "$INSTANCES_DIR/$1/.env" 2>/dev/null | cut -d= -f2-
}

set_ienv() {
  sed -i "s|^$2=.*|$2=$3|" "$INSTANCES_DIR/$1/.env"
}

list_instances() {
  [ -d "$INSTANCES_DIR" ] || return 0
  find "$INSTANCES_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort
}

# first run asks for base domain + ssl email, later runs just load them
reseller_init_conf() {
  mkdir -p "$INSTANCES_DIR"
  if [ ! -f "$MANAGER_CONF" ]; then
    echo ""
    print_step "First-time reseller setup"
    echo -e "  Resellers get subdomains like: ${CYAN}slug.your-base-domain${NC}"
    echo -e "  ${YELLOW}A wildcard DNS record (*.base-domain) must point to this server.${NC}"
    echo ""
    read -rp "  Base domain (e.g., bots.example.com): " BASE_DOMAIN
    if [ -z "$BASE_DOMAIN" ]; then
      print_err "Base domain cannot be empty."
      return 1
    fi
    SSL_EMAIL=$(grep ^SSL_EMAIL= "$ENV_FILE" 2>/dev/null | cut -d= -f2)
    if [ -z "$SSL_EMAIL" ]; then
      read -rp "  Email for SSL: " SSL_EMAIL
    fi
    cat > "$MANAGER_CONF" <<EOF
BASE_DOMAIN=${BASE_DOMAIN}
SSL_EMAIL=${SSL_EMAIL}
EOF
    chmod 600 "$MANAGER_CONF"
    print_ok "Reseller config saved"
  fi
  BASE_DOMAIN=$(grep ^BASE_DOMAIN= "$MANAGER_CONF" | cut -d= -f2)
  SSL_EMAIL=$(grep ^SSL_EMAIL= "$MANAGER_CONF" | cut -d= -f2)
}

# a port counts as taken if something listens on it OR any .env has claimed it
port_in_use() {
  local p="$1" f
  ss -tln 2>/dev/null | awk '{print $4}' | grep -q ":${p}\$" && return 0
  grep -q "^PANEL_PORT=${p}\$" "$ENV_FILE" 2>/dev/null && return 0
  for f in "$INSTANCES_DIR"/*/.env; do
    [ -f "$f" ] || continue
    grep -q "^PANEL_PORT=${p}\$" "$f" && return 0
  done
  return 1
}

find_free_port() {
  local p=8801
  while port_in_use "$p"; do p=$((p + 1)); done
  echo "$p"
}

write_instance_nginx() {
  local slug="$1"
  local domain port
  domain=$(get_ienv "$slug" DOMAIN)
  port=$(get_ienv "$slug" PANEL_PORT)
  cat > "/etc/nginx/sites-available/diako-${slug}" <<EOF
server {
    listen 80;
    server_name ${domain};
    location / {
        proxy_pass         http://127.0.0.1:${port};
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }
}
EOF
  ln -sf "/etc/nginx/sites-available/diako-${slug}" "/etc/nginx/sites-enabled/diako-${slug}"
  nginx -t && systemctl reload nginx
  restore_ssl "$domain"
}

instance_ssl() {
  local slug="$1"
  local domain
  domain=$(get_ienv "$slug" DOMAIN)
  if certbot --nginx -d "$domain" --email "$SSL_EMAIL" --agree-tos --non-interactive --redirect; then
    print_ok "SSL ready for ${domain}"
    (crontab -l 2>/dev/null | grep -v certbot; echo "0 3 * * * certbot renew --quiet && systemctl reload nginx") | crontab -
  else
    print_warn "SSL failed for ${domain} — check DNS, then Edit Settings to retry."
  fi
}

# .env is the single source of truth — this makes the server match it:
# nginx vhost, allowed hosts, ssl cert, containers. no manual follow-up needed.
reseller_apply() {
  local slug="$1" old_domain="$2"
  local domain
  domain=$(get_ienv "$slug" DOMAIN)
  set_ienv "$slug" DJANGO_ALLOWED_HOSTS "$domain"

  print_step "Applying nginx config..."
  write_instance_nginx "$slug"

  if [ -n "$old_domain" ] && [ "$old_domain" != "$domain" ]; then
    print_step "Domain changed ${old_domain} → ${domain}, updating SSL..."
    certbot delete --cert-name "$old_domain" --non-interactive 2>/dev/null || true
    instance_ssl "$slug"
  fi

  print_step "Recreating containers..."
  icompose "$slug" down
  icompose "$slug" up -d
  print_ok "All changes applied for '${slug}'"
}

# numbered picker; sets SELECTED_SLUG, returns 1 on cancel/empty
select_instance() {
  mapfile -t SLUGS < <(list_instances)
  if [ "${#SLUGS[@]}" -eq 0 ]; then
    print_warn "No resellers yet."
    return 1
  fi
  echo ""
  local i=1
  for s in "${SLUGS[@]}"; do
    echo -e "  ${CYAN}$i)${NC} $s  —  $(get_ienv "$s" DOMAIN)"
    i=$((i + 1))
  done
  echo ""
  read -rp "  Select reseller (0 to cancel): " SEL
  if ! [[ "$SEL" =~ ^[0-9]+$ ]] || [ "$SEL" -lt 1 ] || [ "$SEL" -gt "${#SLUGS[@]}" ]; then
    print_warn "Cancelled."
    return 1
  fi
  SELECTED_SLUG="${SLUGS[$((SEL - 1))]}"
}

wait_for_panel() {
  local slug="$1" i
  for i in $(seq 1 30); do
    if icompose "$slug" exec -T panel python -c "print('ok')" &>/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

create_instance_admin() {
  local slug="$1"
  echo ""
  read -rp "  Panel admin username: " ADMIN_USER
  read -rp "  Panel admin email: " ADMIN_EMAIL
  read -rsp "  Panel admin password: " ADMIN_PASS
  echo ""
  if [ -z "$ADMIN_USER" ] || [ -z "$ADMIN_PASS" ]; then
    print_err "Username and password cannot be empty."
    return 1
  fi
  icompose "$slug" exec -T panel python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if User.objects.filter(username='${ADMIN_USER}').exists():
    print('ERROR: Username already exists')
else:
    User.objects.create_superuser('${ADMIN_USER}', '${ADMIN_EMAIL}', '${ADMIN_PASS}')
    print('SUCCESS')
" | grep -q "SUCCESS" && print_ok "Panel admin '${ADMIN_USER}' created ✓" || print_err "Failed — username may already exist."
}

do_reseller_add() {
  check_root
  reseller_init_conf || { press_enter; return; }

  echo ""
  read -rp "  Reseller name (a-z, 0-9, dash — e.g., reseller1): " SLUG
  if ! [[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    print_err "Invalid name — only lowercase letters, digits and dashes."
    press_enter; return
  fi
  if [ -d "$INSTANCES_DIR/$SLUG" ]; then
    print_err "Reseller '$SLUG' already exists."
    press_enter; return
  fi

  read -rp "  Telegram Bot Token: " R_BOT_TOKEN
  read -rp "  Reseller's Telegram Admin ID: " R_ADMIN_ID
  if [ -z "$R_BOT_TOKEN" ] || [ -z "$R_ADMIN_ID" ]; then
    print_err "Token and admin ID cannot be empty."
    press_enter; return
  fi

  AUTO_PORT=$(find_free_port)
  read -rp "  Panel port (Enter for auto: ${AUTO_PORT}): " R_PORT
  if [ -z "$R_PORT" ]; then
    R_PORT="$AUTO_PORT"
  elif port_in_use "$R_PORT"; then
    print_err "Port ${R_PORT} is already taken (by a service or another instance)."
    press_enter; return
  fi

  R_DOMAIN="${SLUG}.${BASE_DOMAIN}"
  R_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || \
             cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 50)

  print_step "Creating instance '${SLUG}'..."
  mkdir -p "$INSTANCES_DIR/$SLUG/shared-data"
  cat > "$INSTANCES_DIR/$SLUG/.env" <<EOF
BOT_TOKEN=${R_BOT_TOKEN}
ADMIN_IDS=${R_ADMIN_ID}
DJANGO_SECRET_KEY=${R_SECRET}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${R_DOMAIN}
PANEL_PORT=${R_PORT}
DOMAIN=${R_DOMAIN}
DB_PATH=/shared-data/bot.db
EOF
  chmod 600 "$INSTANCES_DIR/$SLUG/.env"
  print_ok "Instance files created"

  # shared images are built once by the main install; build here only if missing
  if ! docker image inspect diako-bot:latest &>/dev/null || ! docker image inspect diako-panel:latest &>/dev/null; then
    print_step "Building shared images (first time only)..."
    (cd "$INSTALL_DIR" && docker compose build) || { print_err "Image build failed."; press_enter; return; }
  fi

  print_step "Starting containers..."
  if ! icompose "$SLUG" up -d; then
    print_err "Containers failed to start."
    press_enter; return
  fi
  print_ok "Containers running"

  print_step "Configuring nginx for ${R_DOMAIN}..."
  write_instance_nginx "$SLUG"
  print_ok "Nginx configured"

  print_step "Getting SSL certificate..."
  instance_ssl "$SLUG"

  print_step "Waiting for panel to finish migrations..."
  if wait_for_panel "$SLUG"; then
    create_instance_admin "$SLUG"
  else
    print_warn "Panel not ready yet — create the admin later from the menu."
  fi

  echo ""
  echo -e "  ${BOLD}──────── Reseller '${SLUG}' ready ────────${NC}"
  echo -e "  Panel:  ${GREEN}https://${R_DOMAIN}/diako/dashboard/${NC}"
  echo -e "  Port:   ${CYAN}${R_PORT}${NC} (local only, behind nginx)"
  echo -e "  ${BOLD}──────────────────────────────────────────${NC}"

  press_enter
}

do_reseller_list() {
  mapfile -t SLUGS < <(list_instances)
  if [ "${#SLUGS[@]}" -eq 0 ]; then
    print_warn "No resellers yet."
    press_enter; return
  fi
  # one docker call for all instances — stays fast with 20+ of them
  PS_OUT=$(docker ps -a --format '{{.Names}}|{{.Status}}' 2>/dev/null)
  echo ""
  printf "  ${BOLD}%-16s %-34s %-7s %-12s %-12s${NC}\n" "NAME" "DOMAIN" "PORT" "BOT" "PANEL"
  echo -e "  ─────────────────────────────────────────────────────────────────────────────"
  for s in "${SLUGS[@]}"; do
    DOMAIN=$(get_ienv "$s" DOMAIN)
    PORT=$(get_ienv "$s" PANEL_PORT)
    BOT_ST=$(echo "$PS_OUT" | grep "^diako-${s}-bot" | cut -d'|' -f2 | head -1)
    PANEL_ST=$(echo "$PS_OUT" | grep "^diako-${s}-panel" | cut -d'|' -f2 | head -1)
    fmt_st() {
      case "$1" in
        Up*)  echo -e "${GREEN}● Up${NC}" ;;
        "")   echo -e "${YELLOW}● None${NC}" ;;
        *)    echo -e "${RED}● Down${NC}" ;;
      esac
    }
    printf "  %-16s %-34s %-7s %-23b %-23b\n" "$s" "$DOMAIN" "$PORT" "$(fmt_st "$BOT_ST")" "$(fmt_st "$PANEL_ST")"
  done
  press_enter
}

do_reseller_edit() {
  check_root
  reseller_init_conf || { press_enter; return; }
  select_instance || { press_enter; return; }
  local slug="$SELECTED_SLUG"

  echo ""
  echo -e "  ${BOLD}Settings for '${slug}':${NC}"
  echo -e "    Domain:   ${CYAN}$(get_ienv "$slug" DOMAIN)${NC}"
  echo -e "    Port:     ${CYAN}$(get_ienv "$slug" PANEL_PORT)${NC}"
  echo -e "    Admin ID: ${CYAN}$(get_ienv "$slug" ADMIN_IDS)${NC}"
  echo ""
  echo -e "  ${CYAN}1)${NC} Change domain"
  echo -e "  ${CYAN}2)${NC} Change panel port"
  echo -e "  ${CYAN}3)${NC} Change bot token"
  echo -e "  ${CYAN}4)${NC} Change admin ID"
  echo -e "  ${CYAN}5)${NC} Edit .env manually (nano)"
  echo -e "  ${CYAN}0)${NC} Back"
  echo ""
  read -rp "  Select: " ECHOICE

  local old_domain
  old_domain=$(get_ienv "$slug" DOMAIN)

  case "$ECHOICE" in
    1)
      read -rp "  New domain (full, e.g., name.${BASE_DOMAIN}): " NEW_DOMAIN
      if [ -z "$NEW_DOMAIN" ] || [ "$NEW_DOMAIN" = "$old_domain" ]; then
        print_warn "No change."; press_enter; return
      fi
      set_ienv "$slug" DOMAIN "$NEW_DOMAIN"
      reseller_apply "$slug" "$old_domain"
      ;;
    2)
      read -rp "  New port: " NEW_PORT
      if [ -z "$NEW_PORT" ]; then print_warn "No change."; press_enter; return; fi
      if port_in_use "$NEW_PORT"; then
        print_err "Port ${NEW_PORT} is already taken."
        press_enter; return
      fi
      set_ienv "$slug" PANEL_PORT "$NEW_PORT"
      reseller_apply "$slug"
      ;;
    3)
      read -rp "  New bot token: " NEW_TOKEN
      if [ -z "$NEW_TOKEN" ]; then print_warn "No change."; press_enter; return; fi
      set_ienv "$slug" BOT_TOKEN "$NEW_TOKEN"
      icompose "$slug" up -d bot --force-recreate
      print_ok "Bot token updated and bot restarted"
      ;;
    4)
      read -rp "  New admin ID(s), comma-separated: " NEW_ADMIN
      if [ -z "$NEW_ADMIN" ]; then print_warn "No change."; press_enter; return; fi
      set_ienv "$slug" ADMIN_IDS "$NEW_ADMIN"
      icompose "$slug" up -d bot --force-recreate
      print_ok "Admin ID updated and bot restarted"
      ;;
    5)
      nano "$INSTANCES_DIR/$slug/.env"
      # whatever changed in there, apply takes care of the rest
      reseller_apply "$slug" "$old_domain"
      ;;
    *)
      return
      ;;
  esac
  press_enter
}

do_reseller_ctl() {
  check_root
  select_instance || { press_enter; return; }
  local slug="$SELECTED_SLUG"
  echo ""
  echo -e "  ${CYAN}1)${NC} Start"
  echo -e "  ${CYAN}2)${NC} Stop"
  echo -e "  ${CYAN}3)${NC} Restart"
  echo ""
  read -rp "  Select: " ACT
  case "$ACT" in
    1) icompose "$slug" up -d    && print_ok "'${slug}' started"   ;;
    2) icompose "$slug" stop     && print_ok "'${slug}' stopped"   ;;
    3) icompose "$slug" restart  && print_ok "'${slug}' restarted" ;;
    *) print_warn "Cancelled." ;;
  esac
  press_enter
}

do_reseller_logs() {
  select_instance || { press_enter; return; }
  local slug="$SELECTED_SLUG"
  echo ""
  echo -e "  ${CYAN}1)${NC} Bot logs"
  echo -e "  ${CYAN}2)${NC} Panel logs"
  echo ""
  read -rp "  Select: " ACT
  echo -e "\n${YELLOW}Ctrl+C to exit log${NC}\n"
  case "$ACT" in
    1) icompose "$slug" logs -f bot   ;;
    2) icompose "$slug" logs -f panel ;;
    *) print_warn "Cancelled." ;;
  esac
}

do_reseller_admin() {
  select_instance || { press_enter; return; }
  create_instance_admin "$SELECTED_SLUG"
  press_enter
}

do_reseller_delete() {
  check_root
  select_instance || { press_enter; return; }
  local slug="$SELECTED_SLUG"
  local domain
  domain=$(get_ienv "$slug" DOMAIN)

  echo ""
  echo -e "${RED}${BOLD}⚠ This deletes reseller '${slug}' completely!${NC}"
  echo -e "  Includes: containers, database, settings, nginx config, SSL cert"
  echo ""
  read -rp "  Confirm? Type DELETE: " CONFIRM
  if [ "$CONFIRM" != "DELETE" ]; then
    print_warn "Cancelled."
    press_enter; return
  fi

  print_step "Removing containers..."
  icompose "$slug" down --volumes 2>/dev/null || true

  print_step "Removing files..."
  rm -rf "${INSTANCES_DIR:?}/${slug}"

  print_step "Removing nginx config..."
  rm -f "/etc/nginx/sites-enabled/diako-${slug}" "/etc/nginx/sites-available/diako-${slug}"
  nginx -t && systemctl reload nginx

  if [ -n "$domain" ]; then
    print_step "Removing SSL certificate..."
    certbot delete --cert-name "$domain" --non-interactive 2>/dev/null || true
  fi

  print_ok "Reseller '${slug}' removed"
  press_enter
}

reseller_menu() {
  if ! is_installed; then
    print_err "Install the main project first (option 1)."
    press_enter; return
  fi
  while true; do
    clear
    echo -e "${BLUE}${BOLD}"
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║        👥  Reseller Manager          ║"
    echo "  ╚══════════════════════════════════════╝"
    echo -e "${NC}"
    COUNT=$(list_instances | wc -l)
    echo -e "  Resellers: ${CYAN}${COUNT}${NC}"
    echo ""
    echo -e "  ${BOLD}─────────────────────────────────────${NC}"
    echo -e "  ${CYAN}1)${NC}  Add Reseller"
    echo -e "  ${CYAN}2)${NC}  List Resellers"
    echo -e "  ${CYAN}3)${NC}  Edit Settings"
    echo -e "  ${CYAN}4)${NC}  Start / Stop / Restart"
    echo -e "  ${CYAN}5)${NC}  Logs"
    echo -e "  ${CYAN}6)${NC}  Create Panel Admin"
    echo -e "  ${RED}7)${NC}  Delete Reseller"
    echo -e "  ${BOLD}─────────────────────────────────────${NC}"
    echo -e "  ${CYAN}0)${NC}  Back to main menu"
    echo ""
    read -rp "  Select: " RCHOICE
    case "$RCHOICE" in
      1) do_reseller_add    ;;
      2) do_reseller_list   ;;
      3) do_reseller_edit   ;;
      4) do_reseller_ctl    ;;
      5) do_reseller_logs   ;;
      6) do_reseller_admin  ;;
      7) do_reseller_delete ;;
      0) return ;;
      *) print_warn "Invalid option"; sleep 1 ;;
    esac
  done
}

# ─────────────────────────────────────────────
#  Main Loop
# ─────────────────────────────────────────────

while true; do
  show_menu
  case "$CHOICE" in
    1)  do_install      ;;
    2)  do_update       ;;
    3)  do_restart      ;;
    4)  do_status       ;;
    5)  do_logs_bot     ;;
    6)  do_logs_panel   ;;
    7)  do_ssl          ;;
    8)  do_edit_env     ;;
    9)  do_change_port  ;;
    10) do_create_admin ;;
    11) do_change_domain;;
    12) do_backup       ;;
    13) do_restore      ;;
    14) reseller_menu   ;;
    15) do_uninstall    ;;
    0) clear; echo -e "${GREEN}Goodbye!${NC}\n"; exit 0 ;;
    *) print_warn "Invalid option" ; sleep 1 ;;
  esac
done