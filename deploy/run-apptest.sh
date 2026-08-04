#!/usr/bin/env bash
# Validate hrms + shariah_compliance install/migrate against the custom image.
set -uo pipefail
cd ~/build/erpnext-custom || exit 1

echo "===== UP ====="
docker compose -p erpnext-test -f docker-compose.test.yml up -d

echo "===== WAIT MARIADB ====="
for i in $(seq 1 40); do
  if docker exec erpnext-test-mariadb healthcheck.sh --connect --innodb_initialized >/dev/null 2>&1; then
    echo "mariadb ready after $((i*3))s"; break
  fi
  sleep 3
done

echo "===== FIX TMPFS PERMS (tmpfs mounts land root-owned; bench runs as frappe) ====="
docker exec -u root erpnext-test-backend chown -R frappe:frappe /home/frappe/frappe-bench/sites /home/frappe/frappe-bench/logs

B() { docker exec erpnext-test-backend bash -lc "$1"; }

echo "===== CONFIGURE BENCH ====="
B "bench set-config -g db_host mariadb && bench set-config -gp db_port 3306 && bench set-config -g redis_cache redis://redis-cache:6379 && bench set-config -g redis_queue redis://redis-queue:6379 && bench set-config -g redis_socketio redis://redis-queue:6379"

echo "===== NEW SITE + ERPNEXT ====="
B "bench new-site test.localhost --db-root-username root --mariadb-root-password testpass123 --admin-password admin --db-host mariadb --db-port 3306 --install-app erpnext"
echo "NEWSITE_ERPNEXT_EXIT=$?"

echo "===== INSTALL HRMS ====="
B "bench --site test.localhost install-app hrms"
echo "HRMS_EXIT=$?"

echo "===== INSTALL SHARIAH_COMPLIANCE ====="
B "bench --site test.localhost install-app shariah_compliance"
echo "SHARIAH_EXIT=$?"

echo "===== MIGRATE ====="
B "bench --site test.localhost migrate"
echo "MIGRATE_EXIT=$?"

echo "===== LIST-APPS ====="
B "bench --site test.localhost list-apps"

echo "===== SHARIAH SMOKE (doctypes present?) ====="
B "bench --site test.localhost console <<'PYEOF'
import frappe
print('SHARIAH_DOCTYPES=', frappe.db.count('DocType', {'module': ('like', '%Shariah%')}))
print('CUSTOM_FIELDS_SHARIAH=', frappe.db.count('Custom Field', {'module': ('like', '%Shariah%')}))
try:
    import hijri_converter; print('HIJRI_IMPORT= ok')
except Exception as e:
    print('HIJRI_IMPORT_ERR=', e)
PYEOF"

echo "===== DONE ====="
