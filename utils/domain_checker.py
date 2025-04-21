"""
该脚本的作用：测试当前ip可以访问哪些禁漫域名
"""

from jmcomic import *
import yaml
def get_usable_domain(option_file):

    option = JmOption.from_file(option_file)

    meta_data = {
        # 'proxies': ProxyBuilder.clash_proxy()
    }

    disable_jm_log()


    def get_all_domain():
        template = 'https://jmcmomic.github.io/go/{}.html'
        url_ls = [
            template.format(i)
            for i in range(300, 309)
        ]
        domain_set: Set[str] = set()

        def fetch_domain(url):
            from curl_cffi import requests as postman
            text = postman.get(url, allow_redirects=False, **meta_data).text
            for _domain in JmcomicText.analyse_jm_pub_html(text):
                if _domain.startswith('jm365.work'):
                    continue
                domain_set.add(_domain)

        multi_thread_launcher(
            iter_objs=url_ls,
            apply_each_obj_func=fetch_domain,
        )
        return domain_set


    domain_set = get_all_domain()
    print(f'获取到{len(domain_set)}个域名，开始测试')
    domain_status_dict = {}


    def test_domain(domain: str):
        client = option.new_jm_client(impl='html', domain_list=[domain], **meta_data)
        status = 'ok'

        try:
            client.get_album_detail('123456')
        except Exception as e:
            status = 'fail'
            pass

        domain_status_dict[domain] = status


    multi_thread_launcher(
        iter_objs=domain_set,
        apply_each_obj_func=test_domain,
    )

    for domain, status in domain_status_dict.items():
        print(f'{domain}: {status}')
    return domain_status_dict.items()

# 修改配置文件中的domain
def update_option_domain(option_file: str, domains: List[str]):
    with open(option_file, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if "client" not in data:
        data["client"] = {}
    if "domain" not in data["client"]:
        data["client"]["domain"] = {}
    data["client"]["domain"]["html"] = domains
    with open(option_file, "w", encoding="utf-8") as file:
        yaml.dump(data, file, allow_unicode=True, default_flow_style=False)

# 清除配置文件配置的domain 插件会默认获取domain
def clear_domain(option_file: str):
    with open(option_file, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if "client" in data:
        if "domain" in data["client"]:
            del data["client"]["domain"]
            if "impl" in data["client"]:
                data["client"]["impl"] = "api"
    with open(option_file, "w", encoding="utf-8") as file:
        yaml.dump(data, file, allow_unicode=True, default_flow_style=False)
