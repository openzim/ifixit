#!/usr/bin/env python

from os.path import exists, join, isfile
from os import listdir
import json
import queue
import threading

from ifixittozim import logger, LANGS
from ifixittozim.utils import get_file_content, get_cache_path

items_queue = queue.Queue()

def get_image(image):
    get_file_content(image['original'],cache_file_path)

# Worker, handles each task
def worker():
    while True:
        image = items_queue.get()
        if image is None:
            break
        try:
            remaining_items =  items_queue.qsize()
            if remaining_items % 1000 == 0:
                logger.info("\tAbout {} images remaining".format(remaining_items))
            get_file_content(image['url'],image['path'])
        finally:
            items_queue.task_done()

def start_workers(worker_pool=1000):
    threads = []
    for i in range(worker_pool):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)
    return threads


def stop_workers(threads):
    # stop workers
    for i in threads:
        items_queue.put(None)
    for t in threads:
        t.join()

def get_images(ifixit_api_base_url):

    cache_path = get_cache_path()

    image_guids = dict()

    #for lang in LANGS:
    for lang in ['en']:
        cur_path = join(cache_path, 'categories', lang)
        for category_filename in listdir(cur_path):
        #for category_filename in ['wiki_Mac.json','wiki_Apple Watch.json','wiki_MacBook Pro 15" Retina Display Mid 2015.json']:
            category_path = join(cur_path,category_filename)
            with open(category_path, 'r', encoding='utf-8') as category_file:
                category_content = json.load(category_file)
                if not category_content:
                    continue
                try:
                    if category_content['image']:
                        image_guids[category_content['image']['guid']] = category_content['image']
                        # image_guids.add(category_content['image']['guid'])
                except Exception as e:
                    logger.warning('\tFailed to process {}: {}'.format(category_path, e))

    logger.info('\t{} images found in categories'.format(len(image_guids)))

    #for lang in LANGS:
    for lang in ['en']:
        cur_path = join(cache_path, 'guides', lang)
        for guide_filename in listdir(cur_path):
            guide_path = join(cur_path,guide_filename)
            with open(guide_path, 'r', encoding='utf-8') as guide_file:
                try:
                    guide_content = json.load(guide_file)
                    if not guide_content:
                        continue
                    if guide_content['image']:
                        image_guids[guide_content['image']['guid']] = guide_content['image']
                    # image_guids.add(guide_content['image']['guid'])
                    if guide_content['author']:
                        if guide_content['author']['image']:
                            image_guids[guide_content['author']['image']['guid']] = guide_content['author']['image']
                    for step in guide_content['steps']:
                        if step['media']['type'] != 'image':
                            continue
                        for image in step['media']['data']:
                            image_guids[image['guid']] = image
                            # image_guids.add(image['guid'])
                except Exception as e:
                    logger.warning('\tFailed to process {}: {}'.format(guide_path, e))
    
    logger.info('\t{} images found in categories + guides'.format(len(image_guids)))

    for image_id in image_guids:
        image = image_guids[image_id]
        if 'standard' in image:
            cache_file_path = join(cache_path, 'images', "image_{}.standard".format(image['guid']))
        else:
            cache_file_path = join(cache_path, 'images', "image_{}.full".format(image['guid']))
        if exists(cache_file_path):
            continue
        if 'standard' in image:
            items_queue.put({'url': image['standard'], 'path': cache_file_path})
        else:
            items_queue.put({'url': image['original'], 'path': cache_file_path})
    
    workers = start_workers(worker_pool=100)

    # Blocks until all tasks are complete
    items_queue.join()

    stop_workers(workers)
