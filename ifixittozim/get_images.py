#!/usr/bin/env python

from os.path import exists, join, isfile
from os import listdir
import json

from ifixittozim import logger, LANGS
from ifixittozim.utils import get_file_content, get_cache_path
from ifixittozim.worker import process_work_items, add_work_item, add_work_kind

# dictionary used to store details about images to retrieve
image_guids = dict()

# define the various kind of parallel jobs that are possible
add_work_kind('download_image', download_image)
add_work_kind('list_images_in_category', list_images_in_category)
add_work_kind('list_images_in_guide', list_images_in_guide)
add_work_kind('check_if_image_needs_download', check_if_image_needs_download)

def download_image(work_item):
    get_file_content(work_item['url'],work_item['path'])

# check which images are needed in a given category
def list_images_in_category(work_item):
    category_path = work_item['path']
    with open(category_path, 'r', encoding='utf-8') as category_file:
        category_content = json.load(category_file)
        if not category_content:
            return
        try:
            if 'image' in category_content and category_content['image']:
                image_guids[category_content['image']['guid']] = category_content['image']
        except Exception as e:
            logger.warning('\tFailed to process {}: {}'.format(category_path, e))

# check which images are needed in a given guide
def list_images_in_guide(work_item):
    guide_path = work_item['path']
    with open(guide_path, 'r', encoding='utf-8') as guide_file:
        try:
            guide_content = json.load(guide_file)
            if not guide_content:
                return
            if 'image' in guide_content and guide_content['image']:
                image_guids[guide_content['image']['guid']] = guide_content['image']
            if 'author' in guide_content and guide_content['author']:
                if 'image' in guide_content['author']:
                    image_guids[guide_content['author']['image']['guid']] = guide_content['author']['image']
            if 'steps' in guide_content and guide_content['steps']:
                for step in guide_content['steps']:
                    if step['media']['type'] != 'image':
                        continue
                    for image in step['media']['data']:
                        image_guids[image['guid']] = image
        except Exception as e:
            logger.warning('\tFailed to process {}: {}'.format(guide_path, e))

# check if a needed image is really needed and where to find it + enqueue a work item to download it
def check_if_image_needs_download(work_item):
    image = work_item['image']
    cache_path = work_item['cache_path']
    if 'standard' in image:
        cache_file_path = join(cache_path, 'images', "image_{}.standard".format(image['guid']))
    else:
        cache_file_path = join(cache_path, 'images', "image_{}.full".format(image['guid']))
    if exists(cache_file_path):
        return
    imageAdded = True
    if 'standard' in image:
        add_work_item({'kind': 'download_image', 'url': image['standard'], 'path': cache_file_path})
    else:
        add_work_item({'kind': 'download_image', 'url': image['original'], 'path': cache_file_path})

# enqueue a work item for each category file
def add_work_for_category_files(cache_path):
    #for lang in LANGS:
    for lang in ['en']:
        cur_path = join(cache_path, 'categories', lang)
        for category_filename in listdir(cur_path):
        #for category_filename in ['wiki_Mac.json','wiki_Apple Watch.json','wiki_MacBook Pro 15" Retina Display Mid 2015.json']:
            category_path = join(cur_path,category_filename)
            add_work_item({'kind': 'list_images_in_category', 'path': category_path})

# enqueue a work item for each guide file
def add_work_for_guide_files(cache_path):
    #for lang in LANGS:
    for lang in ['en']:
        cur_path = join(cache_path, 'guides', lang)
        for guide_filename in listdir(cur_path):
        #for guide_filename in ['guide_147263.json']:
            guide_path = join(cur_path,guide_filename)
            add_work_item({'kind': 'list_images_in_guide', 'path': guide_path})

# enqueue a work item for each image seen as needed
def add_work_for_image_check(cache_path):
    for image_id in image_guids:
        image = image_guids[image_id]
        add_work_item({'kind': 'check_if_image_needs_download', 'image': image, 'cache_path': cache_path})

# main function of the package
def get_images():
    
    image_guids.clear()

    cache_path = get_cache_path()

    logger.info('\tExploring artifacts to list images needed'.format(len(image_guids)))
    add_work_for_category_files(cache_path)
    add_work_for_guide_files(cache_path)

    process_work_items(10)

    logger.info('\t{} images found as needed. Downloading necessary ones.'.format(len(image_guids)))

    add_work_for_image_check(cache_path)
    process_work_items(100)
