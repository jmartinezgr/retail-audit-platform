from enum import Enum


class UploadStatus(str, Enum):
    REQUESTED = "REQUESTED"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
