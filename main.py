from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from pathlib import Path
import re
import random
import jmcomic
from pathlib import Path

from .utils import domain_checker, jm_file_resolver
from .utils.jm_options import JmOptions
from .utils.jm_random_search import JmRandomSearch

@register("astrbot_plugin_showmejm", "exneverbur, drdon1234", "适配 AstrBot 的 JM本子 转 PDF 插件，搜漫画，下漫画，看随机漫画！", "2.4")
class ShowMeJM(Star):
    init_options = {
        # 你使用的消息平台, 只能为'napcat', 'llonebot', 'lagrange'
        "platform": 'napcat',
        # 消息平台的域名,端口号和token
        # 使用时需在napcat内配置http服务器 host和port对应好
        'http_host': '127.0.0.1',
        'http_port': 2333,
        # 若消息平台未配置token则留空 否则填写配置的token
        'token': '',
        # 打包成pdf时每批处理的图片数量 每批越小内存占用越小 (仅供参考, 建议按实际调整: 设置为50时峰值占用约1.5G内存, 设置为20时最高占用1G左右)
        'batch_size': 20,
        # 每个pdf中最多有多少个图片 超过此数量时将会创建新的pdf文件 设置为0则不限制, 所有图片都在一个pdf文件中
        'pdf_max_pages': 200,
        # 上传到群文件的哪个目录?默认"/"是传到根目录 如果指定的目录不存在会自动创建文件夹
        # 'group_folder': 'JM漫画',
        'group_folder': '/',
        # 是否开启自动匹配消息中的jm号功能(消息中的所有数字加起来是6~7位数字就触发下载本子) 此功能可能会下载很多不需要的本子占据硬盘, 请谨慎开启
        'auto_find_jm': True,
        # 如果成功找到本子是否停止触发其他插件(Ture:若找到本子则后续其他插件不会触发)
        'prevent_default': True,
        # 配置文件所在位置
        'option': str(Path(__file__).parent / "config.yml"),
        # 是否在启动时获取本子总页数(此功能在插件加载时会访问JM搜索页数, 将会提高随机本子指令的搜索速度)
        'open_random_search': True,
        # 白名单 配置个人白名单和群白名单 若为空或不配置则不启用白名单功能
        # 'person_whitelist': [123456, 654321],
        # 'group_whitelist': [12345678],
    }

    def __init__(self, context: Context):
        super().__init__(context)
        self.options = JmOptions.from_dict(self.init_options)
        file_option = jmcomic.create_option_by_file(self.options.option)
        self.client = file_option.new_jm_client()
        self.api_client = file_option.new_jm_client(impl='api')
        self.random_searcher = JmRandomSearch(self.api_client)

    async def initialize(self):
        if self.options.open_random_search:
            await self.random_searcher.get_max_page()

    @staticmethod
    def parse_command(message: str) -> list:
        parts = message.split(' ')  # 分割命令和参数
        command = parts[0]
        args = []
        if len(parts) > 1:
            args = parts[1:]
        print("接收指令:", command, "参数：", args)
        return args

    @filter.command("jm更新域名")
    async def do_update_domain(self, event: AstrMessageEvent):
        if not self.verify_whitelist(event):
            return

        await event.send(event.plain_result("检查中, 请稍后..."))
        # 自动将可用域名加进配置文件中
        domains = domain_checker.get_usable_domain(self.options.option)
        usable_domains = []
        check_result = "域名连接状态检查完成√\n"
        for domain, status in domains:
            check_result += f"{domain}: {status}\n"
            if status == 'ok':
                usable_domains.append(domain)
        await event.send(event.plain_result(check_result))

        try:
            domain_checker.update_option_domain(self.options.option, usable_domains)
        except Exception as e:
            await event.send(event.plain_result("修改配置文件时发生问题: " + str(e)))
            return

        await event.send(event.plain_result(
            "已将可用域名添加到配置文件中~\n PS:如遇网络原因下载失败, 对我说:'jm清空域名'指令可以将配置文件中的域名清除, 此时我将自动寻找可用域名哦"))

    @filter.command("jm清空域名")
    async def do_clear_domain(self, event: AstrMessageEvent):
        if not self.verify_whitelist(event):
            return

        domain_checker.clear_domain(self.options.option)
        await event.send(event.plain_result(
            "已将默认下载域名全部清空, 我将会自行寻找可用域名\n PS:对我说:'jm更新域名'指令可以查看当前可用域名并添加进配置文件中哦"))

    @filter.command("随机jm")
    async def do_random_download(self, event: AstrMessageEvent):
        if not self.verify_whitelist(event):
            return

        if not self.options.open_random_search:
            await event.send(event.plain_result("随机下载功能未开启"))
            return

        if self.random_searcher.is_max_page_finding:
            await event.send(event.plain_result("正在获取所需数据中, 请稍后再试!"))
            return

        cleaned_text = re.sub(r'@\S+\s*', '', event.message_str).strip()
        args = self.parse_command(cleaned_text)
        tags = ''
        if len(args) == 0:
            await event.send(event.plain_result("正在搜索随机本子，请稍候..."))
        elif len(args) == 1:
            search_query = args[0]
            tags = re.sub(r'[，,]+', ' ', search_query)
            await event.send(event.plain_result(f"正在搜索关键词为 {tags} 随机本子，请稍候..."))
        else:
            await event.send(event.plain_result(f"使用方法不正确，请输入指令 /jm 获取使用说明"))
            return

        max_page = await self.random_searcher.get_max_page(query=tags)
        if max_page == 0:
            await event.send(
                event.plain_result(f"未搜索到任何关键词为 {tags} 随机本子，建议更换为其他语言的相同关键词重新搜索..."))
            return

        random_page = random.randint(1, max_page)
        try:
            result = self.api_client.search_site(search_query=tags, page=random_page)
            album_list = list(result.iter_id_title())
            if not album_list:
                raise ValueError("未找到任何漫画")

            random_index = random.randint(0, len(album_list) - 1)
            selected_album_id = album_list[random_index][0]
            selected_album_title = album_list[random_index][1]

            await event.send(event.plain_result(f"你今天的幸运本子是：[{selected_album_id}]{selected_album_title}，即将开始下载，请稍候..."))
            await jm_file_resolver.before_download(event, self.options, selected_album_id)
        except Exception as e:
            await event.send(event.plain_result(f"随机本子下载失败：{e}"))

    @filter.command("jm")
    async def do_download(self, event: AstrMessageEvent):
        if not self.verify_whitelist(event):
            return

        cleaned_text = re.sub(r'@\S+\s*', '', event.message_str).strip()
        args = self.parse_command(cleaned_text)
        if len(args) == 0:
            help_text = ("你是不是在找: \n"
                        "1.搜索功能: \n"
                        "格式: 查jm [关键词/标签] [页码(默认第一页)]\n"
                        "例: 查jm 鸣潮,+无修正 2\n\n"
                        "2.下载指定id的本子:\n"
                        "格式:jm [jm号]\n"
                        "例: jm 350234\n\n"
                        "3.下载随机本子:\n"
                        "格式:随机jm\n\n"
                        "4.寻找可用下载域名:\n"
                        "格式:jm更新域名\n\n"
                        "5.清除默认域名:\n"
                        "格式:jm清空域名")
            await event.send(event.plain_result(help_text))
            return

        await event.send(event.plain_result(f"即将开始下载{args[0]}, 请稍候..."))
        await jm_file_resolver.before_download(event, self.options, args[0])

    @filter.command("查jm")
    async def do_search(self, event: AstrMessageEvent):
        if not self.verify_whitelist(event):
            return

        cleaned_text = re.sub(r'@\S+\s*', '', event.message_str).strip()
        args = self.parse_command(cleaned_text)
        if len(args) == 0:
            help_text = ("请指定搜索条件, 格式: 查jm [关键词/标签] [页码(默认第一页)]\n"
                        "例: 查jm 鸣潮,+无修正 2\n"
                        "使用提示: 请使用中英文任意逗号隔开每个关键词/标签，切勿使用空格进行分割")
            await event.send(event.plain_result(help_text))
            return

        page = int(args[1]) if len(args) > 1 else 1
        search_query = args[0]
        tags = re.sub(r'[，,]+', ' ', search_query)

        search_page = self.api_client.search_site(search_query=tags, page=page)

        # search_page默认的迭代方式是page.iter_id_title()，每次迭代返回 albun_id, title
        results = []
        for album_id, title in search_page:
            results.append([album_id, title])

        search_result = f"当前为第{page}页\n\n"
        i = 1
        for itemArr in results:
            search_result += f"{i}. [{itemArr[0]}]: {itemArr[1]}\n"
            i += 1

        search_result += "\n对我说jm jm号进行下载吧~"
        await event.send(event.plain_result(search_result))

    async def auto_find_jm(self, event: AstrMessageEvent):
        if not self.options.auto_find_jm:
            return
        
        if not self.verify_whitelist(event):
            return

        cleaned_text = re.sub(r'@\S+\s*', '', event.message_str).strip()
        
        # 检查此消息是否已被其他命令处理过
        if (cleaned_text.startswith('jm更新域名') or 
            cleaned_text.startswith('jm清空域名') or 
            cleaned_text.startswith('随机jm') or 
            cleaned_text.startswith('jm') or 
            cleaned_text.startswith('查jm')):
            return
            
        numbers = re.findall(r'\d+', cleaned_text)
        concatenated_numbers = ''.join(numbers)

        if 6 <= len(concatenated_numbers) <= 7:
            await event.send(event.plain_result(f"你提到了{concatenated_numbers}...对吧?"))
            await jm_file_resolver.before_download(event, self.options, concatenated_numbers)
            return True
        
        return False

    def verify_whitelist(self, event: AstrMessageEvent) -> bool:
        is_group = not event.is_private_chat()
        target = event.get_group_id() if is_group else event.get_sender_id()
        
        if is_group:
            whitelist = self.options.group_whitelist
        else:
            whitelist = self.options.person_whitelist

        if whitelist is None or len(whitelist) == 0:
            return True

        res = target in whitelist
        if not res:
            print(f'该群或好友"{target}"不在白名单中, 停止访问')
        return res

    async def terminate(self):
        pass
