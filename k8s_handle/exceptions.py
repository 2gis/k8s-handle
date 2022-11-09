class ProvisioningError(Exception):
    pass


class ResourceNotAvailableError(Exception):
    pass


class InvalidWarningHeader(Exception):
    pass


class InvalidYamlError(Exception):
    pass


class TemplateRenderingError(Exception):
    pass
