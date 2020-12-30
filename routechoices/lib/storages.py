from django_s3_storage.storage import S3Storage


class OverwriteImageStorage(S3Storage):
    """ Storage that delete a previous file with the same name
    and its copy at different resolution
    """
    def get_available_name(self, name, max_length=None):
        # If the filename already exists,
        # remove it and its copy at different resolution as if it was a true
        # file system
        if self.exists(name):
            self.delete(name)
        return super().get_available_name(name, max_length)

    def url(self, name):
        return '/media/' + name
