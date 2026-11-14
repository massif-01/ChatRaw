"""Private upload/immutable artifact copies, never arbitrary-path downloads."""

import os
import stat
from pathlib import Path

from .store import RunnerError, identifier
from .validation import object_fields, text


class FileStore:
    def __init__(self, store, max_bytes=25 * 1024 * 1024):
        self.store = store
        self.root = store.directory / "files"
        self.root.mkdir(mode=0o700, exist_ok=True)
        self.max_bytes = max_bytes

    def get(self, file_id, session_id=None, kind=None):
        row = self.store.db.execute(
            "SELECT * FROM files WHERE id=?", (file_id,)
        ).fetchone()
        if row is None:
            raise RunnerError("file_not_found", "File not found", 404)
        row = dict(row)
        if (session_id is not None and row["session_id"] != session_id) or (
            kind is not None and row["kind"] != kind
        ):
            raise RunnerError(
                "file_ownership", "File does not belong to this session", 403
            )
        return row

    def path(self, file_id):
        # IDs are generated here, but reject malformed IDs even for internal use.
        if len(file_id) != 32 or any(c not in "0123456789abcdef" for c in file_id):
            raise RunnerError("invalid_file_id", "Invalid file ID")
        return self.root / file_id

    def save(self, session, source, name, mime_type, kind="attachment", run_id=None):
        name = text(name, "filename", 255)
        if "/" in name or "\\" in name or any(ord(c) < 32 for c in name):
            raise RunnerError(
                "invalid_filename",
                "Filename must not contain paths or control characters",
            )
        text(mime_type, "MIME type", 200)
        if any(ord(c) < 32 for c in mime_type):
            raise RunnerError("invalid_mime_type", "Invalid MIME type")
        file_id = identifier()
        path = self.path(file_id)
        total = 0
        try:
            with path.open("xb") as destination:
                os.chmod(path, 0o600)
                while chunk := source.read(min(65536, self.max_bytes + 1 - total)):
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise RunnerError(
                            "file_too_large", "File exceeds the upload limit", 413
                        )
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            self.store.db.execute(
                "INSERT INTO files VALUES (?,?,?,?,?,?,?,?)",
                (
                    file_id,
                    session["id"],
                    session["chat_id"],
                    run_id,
                    kind,
                    name,
                    mime_type,
                    total,
                ),
            )
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return {
            "artifact_id" if kind == "artifact" else "attachment_id": file_id,
            "name": name,
            "mime_type": mime_type,
            "size": total,
        }

    def attachments(self, session, attachments, capabilities):
        result = []
        image_bytes = 0
        image_count = 0
        limits = capabilities.get("limits", {})
        for reference in attachments:
            row = self.get(reference["attachment_id"], session["id"], "attachment")
            image = row["mime_type"].startswith("image/")
            if not capabilities["images" if image else "files"]:
                raise RunnerError(
                    "unsupported_attachment",
                    "Agent does not support this attachment type",
                )
            if image:
                image_count += 1
                if "max_images" in limits and image_count > limits["max_images"]:
                    raise RunnerError(
                        "too_many_images", "Too many images for this Agent"
                    )
                if (
                    "max_image_bytes" in limits
                    and row["size"] > limits["max_image_bytes"]
                ):
                    raise RunnerError(
                        "attachment_too_large",
                        "An image exceeds this Agent's size limit",
                        413,
                    )
                if (
                    "image_mime_types" in limits
                    and row["mime_type"] not in limits["image_mime_types"]
                ):
                    raise RunnerError(
                        "unsupported_attachment",
                        "Agent does not support this image format",
                    )
                image_bytes += row["size"]
                if (
                    "image_total_bytes" in limits
                    and image_bytes > limits["image_total_bytes"]
                ):
                    raise RunnerError(
                        "attachment_too_large",
                        "Images exceed this Agent's per-run limit",
                        413,
                    )
            result.append(
                {
                    "attachment_id": row["id"],
                    "path": self.path(row["id"]),
                    "name": row["name"],
                    "mime_type": row["mime_type"],
                    "size": row["size"],
                }
            )
        return result

    def artifact(self, session, run_id, source):
        object_fields(source, {"path", "name", "mime_type"})
        root = Path(session["workspace"])
        candidate = Path(source["path"])
        if not candidate.is_absolute():
            raise RunnerError("artifact_boundary", "Artifact path must be absolute")
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            raise RunnerError(
                "artifact_boundary", "Artifact must belong to this workspace", 403
            ) from None
        if not relative.parts or any(part in ("..", ".") for part in relative.parts):
            raise RunnerError("artifact_boundary", "Invalid artifact path", 403)
        # Walk using directory FDs and O_NOFOLLOW so a symlink swap cannot turn
        # validation followed by open into an arbitrary host file read.
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for component in relative.parts[:-1]:
                child = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=directory,
                )
                os.close(directory)
                directory = child
            descriptor = os.open(
                relative.parts[-1],
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=directory,
            )
            with os.fdopen(descriptor, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise RunnerError(
                        "artifact_boundary", "Artifact must be a regular file", 403
                    )
                return self.save(
                    session,
                    stream,
                    source["name"],
                    source["mime_type"],
                    "artifact",
                    run_id,
                )
        except OSError:
            raise RunnerError(
                "artifact_boundary", "Artifact could not be safely opened", 403
            ) from None
        finally:
            os.close(directory)
