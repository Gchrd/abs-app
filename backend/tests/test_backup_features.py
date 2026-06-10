import pytest
from fastapi import status
from app.models import Device, Backup
from app.utils.config_sanitizer import sanitize_config
from pathlib import Path

def test_config_sanitizer():
    """Test Richard's Config Sanitizer feature for Cisco and MikroTik."""
    # 1. Test Cisco IOS sanitization
    cisco_raw = (
        "! Last configuration change at 22:04:09 UTC Mon Feb 16 2026 by admin\n"
        "! NVRAM config last updated at 12:00:00 UTC Mon Feb 16 2026 by admin\n"
        "ntp clock-period 360212\n"
        "Current configuration : 1052 bytes\n"
        "! Time: 22:05:00 UTC\n"
        "interface GigabitEthernet1\n"
        " ip address 192.168.1.1 255.255.255.0\n"
    )
    cisco_clean = sanitize_config(cisco_raw, vendor="cisco_ios")
    assert "! Last configuration change at" not in cisco_clean
    assert "! NVRAM config last updated at" not in cisco_clean
    assert "ntp clock-period" not in cisco_clean
    assert "Current configuration :" not in cisco_clean
    assert "! Time: " not in cisco_clean
    assert "interface GigabitEthernet1" in cisco_clean
    assert "ip address 192.168.1.1" in cisco_clean

    # 2. Test MikroTik RouterOS sanitization
    mikrotik_raw = (
        "# feb/16/2026 22:04:09 by RouterOS 6.43.16\n"
        "/ip address\n"
        "add address=192.168.88.1/24 interface=ether1\n"
    )
    mikrotik_clean = sanitize_config(mikrotik_raw, vendor="mikrotik")
    assert "# feb/16/2026 22:04:09 by RouterOS" not in mikrotik_clean
    assert "/ip address" in mikrotik_clean
    assert "add address=192.168.88.1" in mikrotik_clean


def test_active_backup_and_acknowledge_flow(client, admin_headers, db_session):
    """Test Richard's Active Backup and Acknowledge feature flow."""
    db = db_session
    # Create a test device
    dev = Device(
        hostname="test-sw-richard",
        ip="10.10.10.10",
        vendor="cisco_ios",
        protocol="ssh",
        port=22,
        username_enc="dummy",
        password_enc="dummy"
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)

    # Create two successful backups with different hashes
    b1 = Backup(
        device_id=dev.id,
        size_bytes=100,
        hash="hash_old_11111",
        status="success",
        path="/tmp/backup_1.txt"
    )
    b2 = Backup(
        device_id=dev.id,
        size_bytes=110,
        hash="hash_new_22222",
        status="success",
        path="/tmp/backup_2.txt"
    )
    db.add(b1)
    db.add(b2)
    db.commit()
    db.refresh(b1)
    db.refresh(b2)

    # Step 1: Set b1 as the Active Reference Backup
    response = client.put(f"/backups/{b1.id}/set-active", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    
    db.refresh(dev)
    assert dev.active_backup_id == b1.id

    # Step 2: Retrieve active backups list. Since b2 is newer and has a different hash, status_changed should be True
    response = client.get("/backups/active", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    active_list = response.json()
    
    # Find our device in active list
    target_active = next(x for x in active_list if x["device_id"] == dev.id)
    assert target_active["status_changed"] is True
    assert target_active["previous_backup_id"] == b2.id  # b2.id is the newer backup causing the alert

    # Step 3: Acknowledge the change (b2.id) as admin. This should clear the alert.
    response = client.put(f"/backups/{b2.id}/acknowledge", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK

    # Step 4: Retrieve active backups list again. status_changed should now be False!
    response = client.get("/backups/active", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    active_list_new = response.json()
    target_active_new = next(x for x in active_list_new if x["device_id"] == dev.id)
    
    # Alert is cleared because dev.last_ack_backup_id == b2.id
    assert target_active_new["status_changed"] is False
    assert target_active_new["previous_backup_id"] is None


def test_batch_operations_and_safety_locks(client, admin_headers, db_session, tmp_path):
    """Test Richard's Batch ZIP Download and Batch Delete features, including active backup safety locks."""
    db = db_session
    # Create a test device
    dev = Device(
        hostname="test-sw-batch",
        ip="10.10.10.20",
        vendor="cisco_ios",
        protocol="ssh",
        port=22,
        username_enc="dummy",
        password_enc="dummy"
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)

    # Create temporary configuration files on disk
    file1 = tmp_path / "config1.txt"
    file1.write_text("interface Gi0/1\n shutdown")
    file2 = tmp_path / "config2.txt"
    file2.write_text("interface Gi0/1\n no shutdown")

    # Create two backups belonging to batch '2026-05-25'
    b1 = Backup(
        device_id=dev.id,
        size_bytes=30,
        hash="hash_b1",
        status="success",
        path=str(file1),
        batch_id="2026-05-25"
    )
    b2 = Backup(
        device_id=dev.id,
        size_bytes=30,
        hash="hash_b2",
        status="success",
        path=str(file2),
        batch_id="2026-05-25"
    )
    db.add(b1)
    db.add(b2)
    db.commit()
    db.refresh(b1)
    db.refresh(b2)

    # Store backup IDs beforehand so we don't fetch attributes from deleted instances later
    b1_id = b1.id
    b2_id = b2.id

    # Step 1: Test Batch Download Endpoint
    response = client.get("/backups/download-batch/2026-05-25", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/zip"
    assert len(response.content) > 0  # Contains ZIP content

    # Step 2: Test Batch Delete Safety Lock. Set b1 as the Active Reference Backup.
    dev.active_backup_id = b1_id
    db.commit()

    # Try to delete batch. It should fail with 403 Forbidden because b1 is active/locked!
    response = client.delete("/backups/batch/2026-05-25", headers=admin_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "is currently locked/active" in response.json()["detail"]

    # Step 3: Remove the safety lock and delete batch.
    dev.active_backup_id = None
    db.commit()

    response = client.delete("/backups/batch/2026-05-25", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "Successfully deleted 2 backups" in response.json()["message"]

    # Verify backups are removed from database
    assert db.get(Backup, b1_id) is None
    assert db.get(Backup, b2_id) is None
