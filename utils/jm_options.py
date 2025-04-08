class JmOptions:
    __slots__ = ["platform", "http_host", "http_port", "token", "batch_size", "pdf_max_pages", "group_folder",
                 "auto_find_jm", "prevent_default", "option", "open_random_search", "group_whitelist", 'person_whitelist']

    def __init__(
            self,
            platform: str = 'napcat',
            http_host: str = 'localhost',
            http_port: int = 2333,
            token: str = '',
            batch_size: int = 100,
            pdf_max_pages: int = 200,
            group_folder: str = '/',
            auto_find_jm: bool = True,
            prevent_default: bool = True,
            option: str = 'plugins/ShowMeJM/config.yml',
            open_random_search: bool = True,
            group_whitelist: list = None,
            person_whitelist: list = None
    ):
        self.platform = platform
        self.http_host = http_host
        self.http_port = http_port
        self.token = token
        self.batch_size = batch_size
        self.pdf_max_pages = pdf_max_pages
        self.group_folder = group_folder
        self.auto_find_jm = auto_find_jm
        self.prevent_default = prevent_default
        self.option = option
        self.open_random_search = open_random_search
        self.group_whitelist = group_whitelist
        self.person_whitelist = person_whitelist

    @classmethod
    def from_dict(cls, config: dict):
        return cls(
            platform=config.get('platform', 'napcat'),
            http_host=config.get('http_host', 'localhost'),
            http_port=config.get('http_port', 2333),
            token=config.get('token', ''),
            batch_size=config.get('batch_size', 100),
            pdf_max_pages=config.get('pdf_max_pages', 200),
            group_folder=config.get('group_folder', '/'),
            auto_find_jm=config.get('auto_find_jm', True),
            prevent_default=config.get('prevent_default', True),
            option=config.get('option', 'plugins/ShowMeJM/config.yml'),
            open_random_search=config.get('open_random_search', True),
            group_whitelist=config.get('group_whitelist', []),
            person_whitelist=config.get('person_whitelist', [])
        )
