
import queue
import threading

from ifixittozim import logger

items_queue = queue.Queue()
work_kinds = dict()

def add_work_kind(kind, fn):
    work_kinds[kind] = fn

def add_work_item(item):
    if not 'kind' in item:
        raise Exception('Item needs to have a `kind` property defined')
    if not item['kind'] in work_kinds:
        raise Exception('Unknown kind of work, you need to add the work_kind first')
    items_queue.put(item)

def process_work_items(worker_pool=1000):
    if items_queue.empty():
        return
    workers = start_workers(worker_pool)
    # Blocks until all tasks are complete
    items_queue.join()
    stop_workers(workers)

# Worker, handles each task
def worker():
    while True:
        #item = items_queue.get()
        try:
            item = items_queue.get(timeout=0.1)
        except queue.Empty as e:
            continue
        if item is None:
            break
        try:
            remaining_items =  items_queue.qsize()
            if remaining_items % 1000 == 0:
                logger.info("\tAbout {} work items remaining".format(remaining_items))
            work_kinds[item['kind']](item)
        finally:
            items_queue.task_done()

def start_workers(worker_pool):
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