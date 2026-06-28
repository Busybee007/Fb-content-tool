"""
Google Drive integration — read-only mode.

Nhân viên tạo folder con trong Drive, đặt tên bắt đầu bằng barcode.
VD: "SP001 - Áo thun nam", "SP001_ao_thun", "SP001"

App dùng service account để LIST ảnh từ folder đó.

Env vars (dùng một trong hai cách):
  GOOGLE_SERVICE_ACCOUNT_JSON      – đường dẫn đến file key .json (local)
  GOOGLE_SERVICE_ACCOUNT_JSON_B64  – nội dung file key đã base64 (production)
  DRIVE_PARENT_FOLDER_ID           – ID folder cha được share cho service account
"""
import base64
import json
import os
import tempfile

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_PARENT_FOLDER_ID = os.environ.get("DRIVE_PARENT_FOLDER_ID", "")

_service = None
_tmp_key_path = None  # temp file for base64 key (production mode)


def _resolve_key_path() -> str | None:
    """Return path to service account JSON. Supports file path or base64 env var."""
    # Direct file path (local dev)
    path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if path and os.path.exists(path):
        return path

    # Base64-encoded content (production / Render)
    b64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64", "")
    if b64:
        global _tmp_key_path
        if _tmp_key_path and os.path.exists(_tmp_key_path):
            return _tmp_key_path
        data = base64.b64decode(b64)
        # Validate it's valid JSON
        json.loads(data)
        fd, tmp = tempfile.mkstemp(suffix=".json")
        os.write(fd, data)
        os.close(fd)
        _tmp_key_path = tmp
        return tmp

    return None


def is_configured() -> bool:
    p = os.environ.get("DRIVE_PARENT_FOLDER_ID", _PARENT_FOLDER_ID)
    return bool(_resolve_key_path() and p)


def _get_service():
    global _service
    if _service:
        return _service
    key_file = _resolve_key_path()
    if not key_file:
        raise RuntimeError("Drive chưa cấu hình — thiếu GOOGLE_SERVICE_ACCOUNT_JSON hoặc GOOGLE_SERVICE_ACCOUNT_JSON_B64")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
    _service = build("drive", "v3", credentials=creds)
    return _service


def find_barcode_folder(ma_vach: str) -> dict | None:
    """
    Tìm folder con trong DRIVE_PARENT_FOLDER_ID có tên bắt đầu bằng barcode.
    Trả về {"id": ..., "name": ..., "url": ...} hoặc None.
    """
    svc    = _get_service()
    parent = os.environ.get("DRIVE_PARENT_FOLDER_ID", _PARENT_FOLDER_ID)
    safe   = ma_vach.replace("'", "\\'")

    q = (
        f"'{parent}' in parents "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and name contains '{safe}' "
        f"and trashed=false"
    )
    results = svc.files().list(
        q=q,
        fields="files(id,name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    folders = results.get("files", [])
    if not folders:
        return None

    for f in folders:
        name = f["name"]
        if name == ma_vach or name.startswith(ma_vach + " ") or name.startswith(ma_vach + "-") or name.startswith(ma_vach + "_"):
            return {"id": f["id"], "name": name, "url": f"https://drive.google.com/drive/folders/{f['id']}"}
    f = folders[0]
    return {"id": f["id"], "name": f["name"], "url": f"https://drive.google.com/drive/folders/{f['id']}"}


def list_folder_photos(folder_id: str) -> list:
    """List ảnh trong folder, mới nhất trước."""
    svc = _get_service()
    q   = f"'{folder_id}' in parents and trashed=false and mimeType contains 'image/'"
    results = svc.files().list(
        q=q,
        fields="files(id,name,mimeType,createdTime)",
        orderBy="createdTime desc",
        pageSize=200,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    return [
        {
            "file_id":       f["id"],
            "filename":      f["name"],
            "url":           f"https://drive.google.com/uc?id={f['id']}&export=view",
            "thumbnail_url": f"https://drive.google.com/thumbnail?id={f['id']}&sz=w400",
            "created_at":    f.get("createdTime", ""),
        }
        for f in results.get("files", [])
    ]


def list_photos_by_barcode(ma_vach: str) -> tuple[list, dict | None]:
    """Tìm folder theo barcode rồi list ảnh. Trả về (photos, folder_info)."""
    folder = find_barcode_folder(ma_vach)
    if not folder:
        return [], None
    return list_folder_photos(folder["id"]), folder
