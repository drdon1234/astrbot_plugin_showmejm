from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
import re
import random
import jmcomic
from .utils.domain_checker import get_usable_domain, update_option_domain, clear_domain
from .utils.jm_options import JmOptions
from .utils.jm_random_search import JmRandomSearch
from .utils.jm_file_resolver import before_download


@register("astrbot_plugin_showmejm", "exneverbur", "适配 AstrBot 的jm下载插件", "2.4")
class ShowMeJM(Star):
    def __init__(self, context: Context, config: dict):
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
        if len(parts) > 1:
            return parts[1:]
        return []

    @filter.command("jm更新域名")
    async def update_domain(self, event: AstrMessageEvent, cleaned_text: str):
        if not self.verify_whitelist(event):
            return

        await event.send(event.plain_result("检查中, 请稍后..."))
        domains = get_usable_domain(self.options.option)
        usable_domains = []
        check_result = "域名连接状态检查完成√\n"
        for domain, status in domains:
            check_result += f"{domain}: {status}\n"
            if status == 'ok':
                usable_domains.append(domain)

        await event.send(event.plain_result(check_result))

        try:
            update_option_domain(self.options.option, usable_domains)
        except Exception as e:
            await event.send(event.plain_result(f"修改配置文件时发生问题: {str(e)}"))
            return

        await event.send(event.plain_result(
            "已将可用域名添加到配置文件中~\n PS:如遇网络原因下载失败, 对我说:'jm清空域名'指令可以将配置文件中的域名清除, 此时我将自动寻找可用域名哦"))

    @filter.command("jm清空域名")
    async def clear_domain_cmd(self, event: AstrMessageEvent, cleaned_text: str):
        if not self.verify_whitelist(event):
            return

        clear_domain(self.options.option)
        await event.send(event.plain_result(
            "已将默认下载域名全部清空, 我将会自行寻找可用域名\n PS:对我说:'jm更新域名'指令可以查看当前可用域名并添加进配置文件中哦"))

    @filter.command("随机jm")
    async def random_download(self, event: AstrMessageEvent, cleaned_text: str):
        if not self.verify_whitelist(event):
            return

        if not self.options.open_random_search:
            await event.send(event.plain_result("随机下载功能未开启"))
            return

        if self.random_searcher.is_max_page_finding:
            await event.send(event.plain_result("正在获取所需数据中, 请稍后再试!"))
            return

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

            await event.send(event.plain_result(
                f"你今天的幸运本子是：[{selected_album_id}]{selected_album_title}，即将开始下载，请稍候..."))
            await before_download(event, self.options, selected_album_id)
        except Exception as e:
            await event.send(event.plain_result(f"随机本子下载失败：{e}"))

    @filter.command("jm")
    async def download_manga(self, event: AstrMessageEvent, cleaned_text: str):
        if not self.verify_whitelist(event):
            return

        args = self.parse_command(cleaned_text)

        if len(args) == 0:
            await event.send(event.plain_result(
                "你是不是在找: \n"
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
                "格式:jm清空域名"
            ))
            return

        await event.send(event.plain_result(f"即将开始下载{args[0]}, 请稍候..."))
        await before_download(event, self.options, args[0])

    @filter.command("查jm")
    async def search_manga(self, event: AstrMessageEvent, cleaned_text: str):
        if not self.verify_whitelist(event):
            return

        args = self.parse_command(cleaned_text)

        if len(args) == 0:
            await event.send(event.plain_result(
                "请指定搜索条件, 格式: 查jm [关键词/标签] [页码(默认第一页)]\n例: 查jm 鸣潮,+无修正 2\n使用提示: 请使用中英文任意逗号隔开每个关键词/标签，切勿使用空格进行分割"
            ))
            return

        page = int(args[1]) if len(args) > 1 else 1
        search_query = args[0]
        tags = re.sub(r'[，,]+', ' ', search_query)

        search_page = self.api_client.search_site(search_query=tags, page=page)

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

    @filter.message()
    async def auto_find_jm(self, event: AstrMessageEvent, cleaned_text: str):
        if not self.options.auto_find_jm:
            return

        if not self.verify_whitelist(event):
            return

        # 检查是否以命令开头，如果是则忽略
        if any(cleaned_text.startswith(cmd) for cmd in ["jm更新域名", "jm清空域名", "随机jm", "jm", "查jm"]):
            return

        numbers = re.findall(r'\d+', cleaned_text)
        concatenated_numbers = ''.join(numbers)

        if 6 <= len(concatenated_numbers) <= 7:
            await event.send(event.plain_result(f"你提到了{concatenated_numbers}...对吧?"))
            await before_download(event, self.options, concatenated_numbers)

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
