class ProvisioningError(Exception):
    pass


class DeprecationError(Exception):
    pass


class ResourceNotAvailableError(Exception):
    pass


class InvalidYamlError(Exception):
    pass


class TemplateRenderingError(Exception):
    pass
