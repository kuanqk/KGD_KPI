#!/usr/bin/env bash
# Запуск на сервере (bash): собирает контекст для совмещения APPK + KPI и витрины.
# Использование:
#   bash collect_server_context.sh
#   bash collect_server_context.sh > server_snapshot.txt
# Перед отправкой вырежьте пароли/токены, если скрипт случайно вывел секреты.

set -euo pipefail

echo "========== $(date -u +%Y-%m-%dT%H:%M:%SZ) =========="
echo "HOST: $(hostname -f 2>/dev/null || hostname)"
echo "USER: $(whoami)"
echo
echo "----- uname -----"
uname -a || true
echo
echo "----- /opt -----"
ls -la /opt 2>/dev/null || echo "(no /opt or no access)"
echo

for d in /opt/KGD_APPK /opt/KGD_KPI; do
  if [[ -d "$d" ]]; then
    echo "----- tree (depth 2) $d -----"
    find "$d" -maxdepth 2 -type f \( -name 'docker-compose*.yml' -o -name 'compose*.yaml' -o -name '.env' -o -name 'compose*.yml' \) 2>/dev/null | sed 's/^/  /' || true
    echo "----- ls $d -----"
    ls -la "$d" | head -40
    echo
  fi
done

echo "----- docker ps -a -----"
docker ps -a 2>/dev/null || echo "(docker not available)"
echo
echo "----- docker compose ls -----"
docker compose ls 2>/dev/null || true
echo

echo "----- listening TCP (ss) -----"
if command -v ss >/dev/null 2>&1; then
  ss -tlnp 2>/dev/null || ss -tln
else
  netstat -tlnp 2>/dev/null || true
fi
echo

echo "----- nginx: binary + test -----"
command -v nginx >/dev/null 2>&1 && nginx -version 2>&1 || echo "(nginx not in PATH)"
if command -v nginx >/dev/null 2>&1; then
  nginx -t 2>&1 || true
fi
echo "----- nginx configs (paths only) -----"
for d in /etc/nginx/nginx.conf /etc/nginx/conf.d /etc/nginx/sites-enabled; do
  [[ -e "$d" ]] && echo "$d:" && ls -la "$d" 2>/dev/null | head -20
done
echo

echo "----- grep listen / server_name in nginx (first 80 lines each) -----"
for f in /etc/nginx/nginx.conf /etc/nginx/conf.d/*.conf /etc/nginx/sites-enabled/*; do
  [[ -f "$f" ]] || continue
  echo "### $f"
  grep -nE '^\s*(listen|server_name|server\s|location|proxy_pass|root|include)' "$f" 2>/dev/null | head -80 || true
  echo
done

echo "----- systemd units (docker, nginx) -----"
systemctl is-active docker 2>/dev/null || true
systemctl is-active nginx 2>/dev/null || true
echo

echo "----- ufw (if any) -----"
command -v ufw >/dev/null 2>&1 && ufw status || echo "(ufw n/a)"
echo

echo "----- END — пришлите этот вывод (без .env содержимого) -----"
