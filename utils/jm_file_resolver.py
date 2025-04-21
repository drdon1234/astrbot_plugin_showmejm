"""
对文件的下载与打包
"""

import gc
import glob
import os
import re
import shutil
import time
import yaml
import jmcomic
from PIL import Image
from astrbot.api.event import AstrMessageEvent
from .jm_options import JmOptions
from .jm_send_http_request import *

async def before_download(event: AstrMessageEvent, options: JmOptions, manga_id):
    try:
        pdf_files = []
        try:
            pdf_files = download_and_get_pdf(options, manga_id)
        except Exception as e:
            await event.send(event.plain_result("下载时出现问题:" + str(e)))

        print(f"成功保存了{len(pdf_files)}个pdf")
        single_file_flag = len(pdf_files) == 1

        if len(pdf_files) > 0:
            await event.send(event.plain_result("你寻找的本子已经打包发在路上啦, 即将送达~"))
            is_group = not event.is_private_chat()
            await send_files_in_order(options, event, pdf_files, manga_id, single_file_flag, is_group)
        else:
            print("没有找到下载的pdf文件")
            await event.send(event.plain_result("没有找到下载的pdf文件"))
    except Exception as e:
        await event.send(event.plain_result("代码运行时出现问题:" + str(e)))

# 下载图片
def download_and_get_pdf(options: JmOptions, arg):
    # 自定义设置：
    if os.path.exists(options.option):
        load_config = jmcomic.JmOption.from_file(options.option)
    else:
        raise Exception("未检测到JM下载的配置文件")

    album, dler = jmcomic.download_album(arg, load_config)
    downloaded_file_name = album.album_id

    with open(options.option, "r", encoding="utf8") as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    path = os.path.abspath(data["dir_rule"]["base_dir"])

    with os.scandir(path) as entries:
        for entry in entries:
            if entry.is_dir() and downloaded_file_name == entry.name:
                real_name = glob.escape(entry.name)
                pattern = f"{path}/{real_name}*.pdf"
                matches = glob.glob(pattern)
                if len(matches) > 0:
                    print(f"文件：《{entry.name}》 已存在无需转换pdf，直接返回")
                    return matches
                else:
                    print("开始转换：%s " % entry.name)
                    try:
                        return all2PDF(options, os.path.join(path, entry.name), path, entry.name)
                    except Exception as e:
                        print(f"转换pdf时发生错误: {str(e)}")
                        raise e

    return []

def all2PDF(options, input_folder, pdfpath, pdfname):
    start_time = time.time()
    image_paths = []

    # 遍历主目录（自然排序）
    with os.scandir(input_folder) as entries:
        for entry in sorted(entries, key=lambda e: int(e.name) if e.is_dir() and e.name.isdigit() else float('inf')):
            if entry.is_dir():
                # 处理子目录内容（自然排序）
                subdir = os.path.join(input_folder, entry.name)
                with os.scandir(subdir) as sub_entries:
                    for sub_entry in sorted(sub_entries, key=lambda e: int(re.search(r'\d+', e.name).group()) if re.search(r'\d+', e.name) else float('inf')):
                        if sub_entry.is_file():
                            image_paths.append(os.path.join(subdir, sub_entry.name))

    pdf_files = []
    total_pages = len(image_paths)
    pdf_page_size = options.pdf_max_pages if options.pdf_max_pages > 0 else total_pages

    # 分段处理逻辑优化
    for chunk_idx, page_start in enumerate(range(0, total_pages, pdf_page_size), 1):
        chunk = image_paths[page_start:page_start + pdf_page_size]
        
        # 将临时文件和最终文件放在同一目录，只是文件名不同
        temp_pdf = os.path.abspath(os.path.join(pdfpath, f"temp_{pdfname}-{chunk_idx}.pdf"))
        final_pdf = os.path.abspath(os.path.join(pdfpath, f"{pdfname}-{chunk_idx}.pdf"))

        try:
            batch_size = options.batch_size

            # 预加载第一部分
            images = []
            for img_path in chunk[:batch_size]:
                with Image.open(img_path) as img:
                    images.append(img.copy())

            if images:
                try:
                    images[0].save(temp_pdf, format='PDF', save_all=True, append_images=images[1:])
                finally:
                    for img in images:
                        if hasattr(img, "fp") and img.fp is not None:
                            img.close()

            # 添加后续图片
            for i in range(batch_size, len(chunk), batch_size):
                batch = chunk[i:i + batch_size]
                batch_images = [Image.open(img) for img in batch]
                try:
                    images[0].save(temp_pdf, format='PDF', save_all=True, append_images=batch_images, append=True)
                finally:
                    for img in batch_images:
                        if hasattr(img, "fp") and img.fp is not None:
                            img.close()

            # 完成后重命名文件，而不是移动
            os.rename(temp_pdf, final_pdf)
            pdf_files.append(final_pdf)
            print(f"成功生成第{chunk_idx}个PDF: {final_pdf}")
        except (IOError, OSError) as e:
            print(f"图像处理异常: {str(e)}")
            raise Exception(f"PDF生成失败: {e}")
        finally:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
            gc.collect()

    end_time = time.time()
    print(f"总运行时间：{end_time - start_time:.2f}秒")
    return pdf_files

# 按顺序一个一个上传文件 方便阅读
async def send_files_in_order(options: JmOptions, event: AstrMessageEvent, pdf_files, manga_id, single_file_flag, is_group):
    i = 0
    for pdf_path in pdf_files:
        if os.path.exists(pdf_path):
            i += 1
            suffix = '' if single_file_flag else f'-{i}'
            file_name = f"{manga_id}{suffix}.pdf"
            try:
                if is_group:
                    folder_id = await get_group_folder_id(options, event, event.get_group_id(), options.group_folder)
                    await upload_group_file(options, event.get_group_id(), folder_id, pdf_path, file_name)
                else:
                    await upload_private_file(options, event.get_sender_id(), pdf_path, file_name)
                print(f"文件 {file_name} 已成功发送")
            except Exception as e:
                await event.send(event.plain_result(f"发送文件 {file_name} 时出错: {str(e)}"))
                print(f"发送文件 {file_name} 时出错: {str(e)}")

# 获取群文件目录是否存在 并返回目录id
async def get_group_folder_id(options: JmOptions, event: AstrMessageEvent, group_id, folder_name):
    if folder_name == '/':
        return '/'

    data = await get_group_root_files(options, group_id)

    for folder in data.get('folders', []):
        if folder.get('folder_name') == folder_name:
            return folder.get('folder_id')

    # 未找到该文件夹时创建文件夹
    folder_id = await create_group_file_folder(options, group_id, folder_name)
    if folder_id is None:
        data = await get_group_root_files(options, group_id)
        for folder in data.get('folders', []):
            if folder.get('folder_name') == folder_name:
                return folder.get('folder_id')
        return "/"

    return folder_id
