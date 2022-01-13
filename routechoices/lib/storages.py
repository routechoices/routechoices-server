import shutil
import gzip
from django.core.files.base import File
from django_s3_storage.storage import S3Storage, S3File, _wrap_errors


class OverwriteImageStorage(S3Storage):
    """Storage that delete a previous file with the same name
    and its copy at different resolution
    """

    def get_available_name(self, name, max_length=None):
        # If the filename already exists,
        # remove it and its copy at different resolution as if it was a true
        # file system
        if self.exists(name):
            self.delete(name)
        return super().get_available_name(name, max_length)

    def open(self, name, mode="rb", nbytes=None):
        """
        Retrieves the specified file from storage.
        """
        return self._open(name, mode, nbytes)

    @_wrap_errors
    def _open(self, name, mode="rb", nbytes=None):
        if mode != "rb":
            raise ValueError("S3 files can only be opened in read-only mode")
        # Load the key into a temporary file. It would be nice to stream the
        # content, but S3 doesn't support seeking, which is sometimes needed.
        params = self._object_params(name)
        if nbytes and nbytes > 1:
            params["Range"] = f"bytes=0-{nbytes - 1}"
        obj = self.s3_connection.get_object(**params)
        content = self.new_temporary_file()
        shutil.copyfileobj(obj["Body"], content)
        content.seek(0)
        # Un-gzip if required.
        if obj.get("ContentEncoding") == "gzip":
            content = gzip.GzipFile(name, "rb", fileobj=content)
        # All done!
        return S3File(content, name, self)

    def url(self, name):
        return "/media/" + name
