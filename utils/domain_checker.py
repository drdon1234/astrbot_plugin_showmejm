import yaml
from typing import List, Tuple

def get_usable_domain(option_file: str) -> List[Tuple[str, str]]:
    """获取可用域名"""
    from jmcomic import JmOption, multi_thread_launcher, JmcomicText, disable_jm_log
    
    disable_jm_log()
    option = JmOption.from_file(option_file)
    
    # 获取所有可能的域名
    domains = set()
    
    # 从官方页面获取
    template = 'https://jmcmomic.github.io/go/{}.html'
    urls = [template.format(i) for i in range(300, 309)]
    
    def fetch_domain(url):
        try:
            from curl_cffi import requests as postman
            text = postman.get(url, allow_redirects=False).text
            for domain in JmcomicText.analyse_jm_pub_html(text):
                if not domain.startswith('jm365.work'):
                    domains.add(domain)
        except Exception:
            pass
    
    multi_thread_launcher(iter_objs=urls, apply_each_obj_func=fetch_domain)
    
    # 添加备用域名
    backup_domains = ["18comic.vip", "18comic.org", "jmcomic.me", 
                      "jmcomic1.me", "jm-comic.club", "jm-comic.site"]
    domains.update(backup_domains)
    
    # 测试域名是否可用
    domain_status = {}
    
    def test_domain(domain):
        try:
            client = option.new_jm_client(impl='html', domain_list=[domain])
            client.get_album_detail('123456')
            domain_status[domain] = 'ok'
        except Exception:
            domain_status[domain] = 'fail'
    
    multi_thread_launcher(iter_objs=domains, apply_each_obj_func=test_domain, threads=10)
    
    for domain, status in domain_status.items():
        print(f'{domain}: {status}')
    
    return list(domain_status.items())

def update_option_domain(option_file: str, domains: List[str]):
    """更新配置文件中的域名"""
    with open(option_file, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    
    if "client" not in data:
        data["client"] = {}
    
    if "domain" not in data["client"]:
        data["client"]["domain"] = {}
    
    data["client"]["domain"]["html"] = domains
    data["client"]["impl"] = "api"
    
    with open(option_file, "w", encoding="utf-8") as file:
        yaml.dump(data, file, allow_unicode=True, default_flow_style=False)

def clear_domain(option_file: str):
    """清空配置文件中的域名设置"""
    with open(option_file, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    
    if "client" in data:
        if "domain" in data["client"]:
            del data["client"]["domain"]
        data["client"]["impl"] = "api"
    
    with open(option_file, "w", encoding="utf-8") as file:
        yaml.dump(data, file, allow_unicode=True, default_flow_style=False)
