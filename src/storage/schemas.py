from pydantic import BaseModel


class UploadResponse(BaseModel):
    file_url: str
    file_path: str
    bucket: str


class DeleteRequest(BaseModel):
    file_path: str
