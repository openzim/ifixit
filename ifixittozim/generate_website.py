from os.path import abspath, dirname, join
from os import listdir
from datetime import datetime
import json
import re
import traceback

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ifixittozim import logger, LANGS
from ifixittozim.utils import get_dist_path, get_cache_path, setlocale

def guides_in_progress(guides, in_progress=True):
    if in_progress:
        return [guide for guide in guides if 'GUIDE_IN_PROGRESS' in guide['flags']]
    else:
        return [guide for guide in guides if 'GUIDE_IN_PROGRESS' not in guide['flags']]

# TODO: Move images to the appropriate folder + handle unusual extensions ? (or is it just a corner case ?)                                         
def get_guide_image_path(guide):
    if guide['image'] and guide['image']['guid']:
        return '../../../cache/images/image_{}.standard'.format(guide['image']['guid'])
    else:
        return '../../shared/GuideNoImage_300x225.jpg'


def generate_website():
    env = Environment(
        loader=FileSystemLoader(join(abspath(dirname(__file__)), '..', 'templates'), encoding='utf8'),
        autoescape=select_autoescape()
    )
    env.filters["guides_in_progress"] = guides_in_progress
    env.filters["get_guide_image_path"] = get_guide_image_path

    cache_path = get_cache_path()
    dist_path = get_dist_path()
    
    guide_template = env.get_template("guide.html")
    category_template = env.get_template("category.html")

    guide_label={
        'en': {
            'written_by': 'Written By:',
            'difficulty': 'Difficulty',
            'steps': 'Steps',
            'time_required': ' Time Required',
            'sections': 'Sections',
            'flags': 'Flags',
            'introduction': 'Introduction',
            'step_no': 'Step ',
            'conclusion': 'Conclusion',
            'author': 'Author',
            'reputation': 'Reputation',
            'member_since': 'Member since: ',
        },
        'fr': {
            'written_by': 'Rédigé par :',
            'difficulty': 'Difficulté',
            'steps': 'Étapes',
            'time_required': 'Temps nécessaire',
            'sections': 'Sections',
            'flags': 'Drapeaux',
            'introduction': 'Introduction',
            'step_no': 'Étape ',
            'conclusion': 'Conclusion',
            'author': 'Auteur',
            'reputation': 'Réputation',
            'member_since': 'Membre depuis le ',
        }
    }

    category_label={
        'en': {
            'author': 'Author: ',
            'categories': ' Categories',
            'featured_guides': 'Featured Guides',
            'technique_guides': 'Techniques',
            'replacement_guides': 'Replacement Guides',
            'teardown_guides': 'Teardowns',
            'related_pages': 'Related Pages',
            'in_progress_guides': 'In Progress Guides',
            'disassembly_guides': 'Disassembly Guides',
            'repairability': 'Repairability:',
        }
    }
    guide_regex_full = re.compile(r'href=\"https://\w*\.ifixit\.\w*/Guide/.*/(?P<guide_id>\d*)\"')
    guide_regex_rel = re.compile(r'href=\"/Guide/.*/(?P<guide_id>\d*).*?\"')
    content_image_regex = re.compile(r'\"(?P<prefix>https://guide-images\.cdn\.ifixit\.com/igi/)(?P<image_filename>\w*?.\w*?)\"')
    device_link_regex = re.compile(r'href=\"/Device/(?P<device>.*?)\"')
        
    num_guide = 1
    for lang in ['en']:
        cur_path = join(cache_path, 'guides', lang)
        #files_to_process = listdir(cur_path)
        files_to_process = ['guide_26254.json', 'guide_437.json', 'guide_122924.json', 'guide_101194.json', 'guide_131963.json', 'guide_61205.json', 'guide_131072.json', 'guide_38783.json', 'guide_125834.json', 'guide_11677.json', 'guide_41080.json', 'guide_41084.json', 'guide_41082.json', 'guide_41083.json']
        #files_to_process = []
        for guide_filename in files_to_process:
            guide_path = join(cur_path,guide_filename)
            with open(guide_path, 'r', encoding='utf-8') as guide_file:
                guide_content = json.load(guide_file)
                if not guide_content:
                    continue   
                try:                
                    if guide_content['difficulty'] == 'Very easy':
                        guide_content['difficulty_class'] = 'difficulty-1'
                    elif guide_content['difficulty'] == 'Easy':
                        guide_content['difficulty_class'] = 'difficulty-2'
                    elif guide_content['difficulty'] == 'Moderate':
                        guide_content['difficulty_class'] = 'difficulty-3'
                    elif guide_content['difficulty'] == 'Difficult':
                        guide_content['difficulty_class'] = 'difficulty-4'
                    elif guide_content['difficulty'] == 'Very difficult':
                        guide_content['difficulty_class'] = 'difficulty-5'
                    else:
                        raise Exception("Unknown guide difficulty: '{}' in guide {}".format(guide_content['difficulty'],guide_content['guideid']))
                    with setlocale('en_GB'):
                        if guide_content['author']['join_date']:
                            guide_content['author']['join_date_rendered']=datetime.strftime(datetime.fromtimestamp(guide_content['author']['join_date']),'%x')
                    guide_content['introduction_rendered'] = guide_regex_full.sub('href="./guide_\\g<guide_id>.html"',guide_content['introduction_rendered'])
                    guide_content['introduction_rendered'] = guide_regex_rel.sub('href="./guide_\\g<guide_id>.html"',guide_content['introduction_rendered'])
                    guide_content['conclusion_rendered'] = guide_regex_full.sub('href="./guide_\\g<guide_id>.html"',guide_content['conclusion_rendered'])
                    guide_content['conclusion_rendered'] = guide_regex_rel.sub('href="./guide_\\g<guide_id>.html"',guide_content['conclusion_rendered'])
                    for step in guide_content['steps']:
                        if not step['media']:
                            raise Exception("Missing media attribute in step {} of guide {}".format(step['stepid'],guide_content['guideid']))
                        if step['media']['type'] not in ['image', 'video', 'embed']:
                            raise Exception("Unrecognized media type in step {} of guide {}".format(step['stepid'],guide_content['guideid']))
                        if step['media']['type'] == 'video':
                            if 'data' not in step['media'] or not step['media']['data']:
                                raise Exception("Missing 'data' in step {} of guide {}".format(step['stepid'],guide_content['guideid']))
                            if 'image' not in step['media']['data'] or not step['media']['data']['image']:
                                raise Exception("Missing outer 'image' in step {} of guide {}".format(step['stepid'],guide_content['guideid']))
                            if 'image' not in step['media']['data']['image'] or not step['media']['data']['image']['image']:
                                raise Exception("Missing inner 'image' in step {} of guide {}".format(step['stepid'],guide_content['guideid']))
                        if step['media']['type'] == 'embed':
                            if 'data' not in step['media'] or not step['media']['data']:
                                raise Exception("Missing 'data' in step {} of guide {}".format(step['stepid'],guide_content['guideid']))
                            if 'html' not in step['media']['data'] or not step['media']['data']['html']:
                                raise Exception("Missing 'html' in step {} of guide {}".format(step['stepid'],guide_content['guideid']))
                        for line in step['lines']:
                            if not line['bullet'] in ['black', 'red', 'orange', 'yellow', 'green', 'blue', 'light_blue', 'violet', 'icon_note', 'icon_caution', 'icon_caution', 'icon_reminder']:
                                raise Exception("Unrecognized bullet '{}' in step {} of guide {}".format(line['bullet'], step['stepid'],guide_content['guideid']))
                            line['text_rendered'] = guide_regex_full.sub('href="./guide_\\g<guide_id>.html"',line['text_rendered'])
                            line['text_rendered'] = guide_regex_rel.sub('href="./guide_\\g<guide_id>.html"',line['text_rendered'])
                    guide_rendered = guide_template.render(guide=guide_content, label=guide_label[lang])
                    guide_path = join(dist_path, 'guides', lang, 'guide_{}.html'.format(guide_content['guideid']))
                    with open(guide_path, "w") as fh:
                        fh.write(guide_rendered)
                except Exception as ex:
                    logger.warning('\tFailed to process {}: {}'.format(guide_path, ex))
                    traceback.print_exc()
            num_guide += 1
            if (num_guide % 100 == 0):
                logger.info("{} guides rendered out of {}".format(num_guide, len(files_to_process)))

        num_category = 1
        cur_path = join(cache_path, 'categories', lang)
        #files_to_process = listdir(cur_path)
        #files_to_process = ['wiki_Coolpad 3300A.json','wiki_Western Digital External Storage.json','wiki_Apple Watch.json','wiki_MacBook Pro 15" Retina Display Mid 2015.json','wiki_Mac.json']
        files_to_process = []
        for category_filename in files_to_process:
            category_path = join(cur_path,category_filename)
            with open(category_path, 'r', encoding='utf-8') as category_file:
                category_content = json.load(category_file)
                if not category_content:
                    continue
                try:
                    for guide in category_content['featured_guides']:
                        if guide['type'] not in ['replacement', 'technique', 'teardown', 'disassembly']:
                            raise Exception('Unsupported type of guide: {} for featured_guide {}'.format(guide['type'], guide['guideid']))
                    for guide in category_content['guides']:
                        if guide['type'] not in ['replacement', 'technique', 'teardown', 'disassembly']:
                            raise Exception('Unsupported type of guide: {} for guide {}'.format(guide['type'], guide['guideid']))
                    category_content['contents_rendered'] = content_image_regex.sub('../../../cache/images/image_\\g<image_filename>',category_content['contents_rendered'])
                    category_content['contents_rendered'] = device_link_regex.sub('href="./category_\\g<device>.html"',category_content['contents_rendered'])
                    category_content['filename'] = re.sub("\s", "_", category_content['title'])
                    for idx, child in enumerate(category_content['children']):
                        category_content['children'][idx]['filename'] = re.sub("\s", "_", category_content['children'][idx]['title'])
                    category_rendered = category_template.render(category=category_content, label=category_label[lang], lang=lang)
                    category_path = join(dist_path, 'categories', lang, 'category_{}.html'.format(category_content['filename']))
                    with open(category_path, "w") as fh:
                        fh.write(category_rendered)
                except Exception as e:
                    logger.warning('\tFailed to process {}:\n{}'.format(category_path, e))
            num_category += 1
            if (num_category % 100 == 0):
                logger.info("{} categories rendered out of {}".format(num_category, len(files_to_process)))

    
    