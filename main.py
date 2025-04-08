from pkg.platform.types import MessageChain, Image
from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
from jmcomic import JmSearchPage, JmOption
import re
import random

import jmcomic
from plugins.ShowMeJM.utils import domain_checker, jm_file_resolver
from plugins.ShowMeJM.utils.jm_options import JmOptions
from plugins.ShowMeJM.utils.jm_random_search import JmRandomSearch


# 注册插件
@register(name="ShowMeJM", description="jm下载", version="2.4", author="exneverbur")
class MyPlugin(BasePlugin):
    init_options = {
        # 你使用的消息平台, 只能为'napcat', 'llonebot', 'lagrange'
        "platform": 'napcat',
        # 消息平台的域名,端口号和token
        # 使用时需在napcat内配置http服务器 host和port对应好
        'http_host': 'localhost',
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
        'option': 'plugins/ShowMeJM/config.yml',
        # 是否在启动时获取本子总页数(此功能在插件加载时会访问JM搜索页数, 将会提高随机本子指令的搜索速度)
        'open_random_search': True,
        # 白名单 配置个人白名单和群白名单 若为空或不配置则不启用白名单功能
        # 'person_whitelist': [123456, 654321],
        # 'group_whitelist': [12345678],
    }

    # 插件加载时触发
    def __init__(self, host: APIHost):
        super().__init__(host)
        self.options = JmOptions.from_dict(self.init_options)
        file_option = jmcomic.create_option_by_file(self.options.option)
        self.client = file_option.new_jm_client()
        self.api_client = file_option.new_jm_client(impl='api')
        self.random_searcher = JmRandomSearch(self.api_client)

    # 异步初始化插件时触发
    async def initialize(self):
        if self.options.open_random_search:
            await self.random_searcher.get_max_page()

    @handler(PersonNormalMessageReceived)
    @handler(GroupNormalMessageReceived)
    async def message_received(self, ctx: EventContext):
        receive_text = ctx.event.text_message
        cleaned_text = re.sub(r'@\S+\s*', '', receive_text).strip()
        prevent_default = [self.options.prevent_default]
        if cleaned_text.startswith('jm更新域名'):
            await self.execute_if_allowed(ctx, prevent_default, lambda: self.do_update_domain(ctx))
        elif cleaned_text.startswith('jm清空域名'):
            await self.execute_if_allowed(ctx, prevent_default, lambda: self.do_clear_domain(ctx))
        elif cleaned_text.startswith('随机jm'):
            await self.execute_if_allowed(ctx, prevent_default, lambda: self.do_random_download(ctx, cleaned_text))
        elif cleaned_text.startswith('jm'):
            await self.execute_if_allowed(ctx, prevent_default, lambda: self.do_download(ctx, cleaned_text))
        elif cleaned_text.startswith('查jm'):
            await self.execute_if_allowed(ctx, prevent_default, lambda: self.do_search(ctx, cleaned_text))
        # 匹配消息中包含的 6~7 位数字
        elif self.options.auto_find_jm:
            prevent_default[0] = False
            matched = await self.execute_if_allowed(ctx, prevent_default, lambda: self.do_auto_find_jm(ctx, cleaned_text))
            if matched and self.options.prevent_default:
                prevent_default[0] = True
        else:
            # 未匹配上任何指令 说明此次消息与本插件无关
            prevent_default[0] = False
        if prevent_default[0]:
            # 阻止该事件默认行为（向接口获取回复）
            ctx.prevent_default()

    # 插件卸载时触发
    def __del__(self):
        pass

    # 更新域名
    async def do_update_domain(self, ctx: EventContext):
        await ctx.reply(MessageChain(["检查中, 请稍后..."]))
        # 自动将可用域名加进配置文件中
        domains = domain_checker.get_usable_domain(self.options.option)
        usable_domains = []
        check_result = "域名连接状态检查完成√\n"
        for domain, status in domains:
            check_result += f"{domain}: {status}\n"
            if status == 'ok':
                usable_domains.append(domain)
        await ctx.reply(MessageChain([check_result]))
        try:
            domain_checker.update_option_domain(self.options.option, usable_domains)
        except Exception as e:
            await ctx.reply(MessageChain(["修改配置文件时发生问题: " + str(e)]))
            return
        await ctx.reply(MessageChain([
            "已将可用域名添加到配置文件中~\n PS:如遇网络原因下载失败, 对我说:'jm清空域名'指令可以将配置文件中的域名清除, 此时我将自动寻找可用域名哦"]))

    # 清空域名
    async def do_clear_domain(self, ctx: EventContext):
        domain_checker.clear_domain(self.options.option)
        await ctx.reply(MessageChain([
            "已将默认下载域名全部清空, 我将会自行寻找可用域名\n PS:对我说:'jm更新域名'指令可以查看当前可用域名并添加进配置文件中哦"]))

    # 随机下载漫画
    async def do_random_download(self, ctx: EventContext, cleaned_text: str):
        if not self.options.open_random_search:
            await ctx.reply(MessageChain(["随机下载功能未开启"]))
            return
        if self.random_searcher.is_max_page_finding:
            await ctx.reply(MessageChain(["正在获取所需数据中, 请稍后再试!"]))
            return
        args = parse_command(ctx, cleaned_text)
        tags = ''
        if len(args) == 0:
            await ctx.reply(MessageChain(["正在搜索随机本子，请稍候..."]))
        elif len(args) == 1:
            search_query = args[0]
            tags = re.sub(r'[，,]+', ' ', search_query)
            await ctx.reply(MessageChain([f"正在搜索关键词为 {tags} 随机本子，请稍候..."]))
        else:
            await ctx.reply(MessageChain([f"使用方法不正确，请输入指令 /jm 获取使用说明"]))
            return
        max_page = await self.random_searcher.get_max_page(query=tags)
        if max_page == 0:
            await ctx.reply(
                MessageChain([f"未搜索到任何关键词为 {tags} 随机本子，建议更换为其他语言的相同关键词重新搜索..."]))
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
            await ctx.reply(MessageChain([f"你今天的幸运本子是：[{selected_album_id}]{selected_album_title}，即将开始下载，请稍候..."]))
            await jm_file_resolver.before_download(ctx, self.options, selected_album_id)
        except Exception as e:
            await ctx.reply(MessageChain([f"随机本子下载失败：{e}"]))

    # 下载漫画
    async def do_download(self, ctx: EventContext, cleaned_text: str):
        args = parse_command(ctx, cleaned_text)
        if len(args) == 0:
            await ctx.reply(MessageChain([
                "你是不是在找: \n""1.搜索功能: \n""格式: 查jm [关键词/标签] [页码(默认第一页)]\n""例: 查jm 鸣潮,+无修正 2\n\n""2.下载指定id的本子:\n""格式:jm [jm号]\n""例: jm 350234\n\n""3.下载随机本子:\n""格式:随机jm\n\n""4.寻找可用下载域名:\n""格式:jm更新域名\n\n""5.清除默认域名:\n""格式:jm清空域名"]))
            if self.options.prevent_default:
                # 阻止该事件默认行为（向接口获取回复）
                ctx.prevent_default()
            return
        await ctx.reply(MessageChain([f"即将开始下载{args[0]}, 请稍候..."]))
        await jm_file_resolver.before_download(ctx, self.options, args[0])

    # 执行JM的搜索
    async def do_search(self, ctx: EventContext, cleaned_text: str):
        args = parse_command(ctx, cleaned_text)
        if len(args) == 0:
            # image_path = os.path.join(self.cache_dir, "jmSearch.png")
            # if os.path.exists(image_path):
            #     await ctx.reply(MessageChain([Image(path=image_path)]))
            await ctx.reply(MessageChain(
                [
                    "请指定搜索条件, 格式: 查jm [关键词/标签] [页码(默认第一页)]\n例: 查jm 鸣潮,+无修正 2\n使用提示: 请使用中英文任意逗号隔开每个关键词/标签，切勿使用空格进行分割"]))
            return
        page = int(args[1]) if len(args) > 1 else 1
        search_query = args[0]
        tags = re.sub(r'[，,]+', ' ', search_query)
        search_page: JmSearchPage = self.api_client.search_site(search_query=tags, page=page)
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
        await ctx.reply(MessageChain([search_result]))

    # 匹配逆天文案
    async def do_auto_find_jm(self, ctx: EventContext, cleaned_text: str):
        numbers = re.findall(r'\d+', cleaned_text)
        concatenated_numbers = ''.join(numbers)
        if 6 <= len(concatenated_numbers) <= 7:
            await ctx.reply(MessageChain([f"你提到了{concatenated_numbers}...对吧?"]))
            await jm_file_resolver.before_download(ctx, self.options, concatenated_numbers)
            return True
        return False

    # 校验白名单权限
    async def execute_if_allowed(self, ctx: EventContext, prevent_default, action):
        if ctx.event.launcher_type == "person":
            is_group = False
            target = ctx.event.sender_id
        else:
            is_group = True
            target = ctx.event.launcher_id

        if self.verify_whitelist(is_group, target):
            return await action()
        prevent_default[0] = False
        return None

    def verify_whitelist(self, is_group: bool, target):
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



def parse_command(ctx: EventContext, message: str):
    parts = message.split(' ')  # 分割命令和参数
    command = parts[0]
    args = []
    if len(parts) > 1:
        args = parts[1:]
    print("接收指令:", command, "参数：", args)
    return args
