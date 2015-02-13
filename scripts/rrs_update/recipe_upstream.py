# -*- coding: utf-8 -*-
import re
import threading
from multiprocessing import cpu_count
from datetime import datetime

from django.db import transaction
from rrs.models import RecipeUpstream, RecipeUpstreamHistory

git_regex = re.compile("(?P<gprefix>(v|))(?P<gver>((\d+[\.\-_]*)+))(?P<gmiddle>(\+|)(git|)(r|)(AUTOINC|)(\+|))(?P<ghash>.*)")

"""
    Update Recipe upstream information searching in upstream sites.
    Adds information only when the version changes.
"""
def update_recipe_upstream(envdata, logger):
    history = RecipeUpstreamHistory(start_date = datetime.now())

    result = get_upstream_info(envdata, logger)

    history.end_date = datetime.now()
    history.save()

    transaction.enter_transaction_management()
    transaction.managed(True)

    for recipe, recipe_result in result.iteritems():
        create_recipe_upstream(recipe, recipe_result, history, logger)

    transaction.commit()
    transaction.leave_transaction_management()

def create_recipe_upstream(recipe, recipe_result, history, logger):
    recipe_upstream = RecipeUpstream()
    recipe_upstream.recipe = recipe
    recipe_upstream.history = history
    recipe_upstream.version = recipe_result['version']
    recipe_upstream.type = recipe_result['type']
    recipe_upstream.status = recipe_result['status']
    recipe_upstream.no_update_reason = recipe_result['no_update_reason']
    recipe_upstream.date = recipe_result['date']
    recipe_upstream.save()

"""
    Get upstream info for all Recipes.
"""
def get_upstream_info(envdata, logger):
    class GenericThread(threading.Thread):
        def __init__(self, function):
            threading.Thread.__init__(self)
            self.function = function
    
        def run(self):
            self.function()

    envdata_tmp = envdata.copy()
    result = {}

    recipe_mutex = threading.Lock()
    result_mutex = threading.Lock()

    # Find upstream versions in parallel use threads = cpu_count
    # since tasks are not CPU intensive
    threads = []
    thread_count = cpu_count()

    for t in range(0, thread_count):
        threads.append(GenericThread(lambda: get_upstream_info_thread(envdata_tmp, result, recipe_mutex, result_mutex, logger)))

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    return result

def get_upstream_info_thread(envdata, result, recipe_mutex, result_mutex, logger):
    from datetime import datetime

    def vercmp_string(a, b, recipe_type):
        cmp_result = None

        if recipe_type == 'git':
            match_a = git_regex.match(a)
            match_b = git_regex.match(b)

            if match_a and match_b:
                cmp_result = bb.utils.vercmp_string(match_a.group('gver'),
                                match_b.group('gver'))
    
        if cmp_result is None:
            cmp_result = bb.utils.vercmp_string(a, b)

        return cmp_result

    while True:
        recipe = None
        data = None
        recipe_type = None
        recipe_uri = None

        recipe_mutex.acquire()
        if len(envdata) == 0:
            recipe_mutex.release()
            break

        recipe = envdata.items()[0][0]
        data = envdata[recipe]

        del envdata[recipe]
        recipe_mutex.release()

        # Get recipe SRC_URI and type
        found = 0
        for uri in data.getVar("SRC_URI", True).split():
            m = re.compile('(?P<type>[^:]*)').match(uri)
            if not m:
                raise MalformedUrl(uri)
            elif m.group('type') in ('http', 'https', 'ftp', 'cvs', 'svn', 'git'):
                found = 1
                recipe_uri = uri
                recipe_type = m.group('type')
                break
        if not found:
                recipe_type = "file"

        recipe_pv = data.getVar('PV', True)

        # Build result dictionary (version, type, status, no_update_reason, date, save),
        # for types see RecipeUpstream.RECIPE_UPSTREAM_TYPE_CHOICES,
        # for status see RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES.
        recipe_result = {}
        recipe_result['version'] = ''
        recipe_result['type'] = ''
        recipe_result['status'] = ''
        recipe_result['no_update_reason'] = ''
        recipe_result['date'] = ''

        manual_upstream_version = data.getVar("RECIPE_UPSTREAM_VERSION", True)
        if manual_upstream_version:
            recipe_result['version'] = manual_upstream_version
            recipe_result['type'] = 'M'

            manual_upstream_date = data.getVar("CHECK_DATE", True)
            if manual_upstream_date:
                date = datetime.strptime(manual_upstream_date, "%b %d, %Y")
            else:
                date = datetime.utcnow()
            recipe_result['date'] = date
        elif recipe_type == "file": 
            # files are always uptodate
            recipe_result['version'] = recipe_pv
            recipe_result['type'] = 'A'
            recipe_result['date'] = datetime.utcnow()
        elif recipe_type in ['http', 'https', 'ftp', 'git']:
            try:
                ud = bb.fetch2.FetchData(recipe_uri, data)

                pupver = ud.method.latest_versionstring(ud, data)
                if (pupver == ''): # try to find again due to timeout errors
                    pupver = ud.method.latest_versionstring(ud, data) 

                if recipe_type == 'git':
                    git_regex_match = git_regex.match(recipe_pv)

                    if git_regex_match:
                        pupver = git_regex_match.group('gprefix') + pupver

                        if not pupver:
                            pupver = git_regex_match.group('gver')

                        pupver += git_regex_match.group('gmiddle')

                        latest_revision = ud.method.latest_revision(ud, data, ud.names[0])
                        if git_regex_match.group('ghash') == 'X':
                            pupver += 'AUTOINC+' + latest_revision[:10]
                        else:
                            pupver += latest_revision[:len(git_regex_match.group('ghash'))]

                recipe_result['version'] = pupver
                recipe_result['type'] = 'A'
                recipe_result['date'] = datetime.utcnow()
            except Exception as inst:
                import sys, traceback
                logger.warn("get_upstream_info, recipe %s, pv %s, unexpected error: %s" 
                            % (recipe.pn, recipe_pv, repr(inst)))
                print '-' * 60
                traceback.print_exc(file=sys.stdout)
                print '-' * 60

                recipe_result['date'] = datetime.utcnow()
        else:
            logger.warn("get_upstream_info, recipe %s protocol %s isn't implemented"
                         % (str(recipe.pn), recipe_type))

            recipe_result['date'] = datetime.utcnow()

        no_update_reason = data.getVar("RECIPE_NO_UPDATE_REASON", True) or ''
        recipe_result['no_update_reason'] = no_update_reason

        if not recipe_result['version']:
            recipe_result['status'] = 'U' # Unknown, need to review why
        elif vercmp_string(recipe_pv, recipe_result['version'], recipe_type) == -1:
            recipe_result['status'] = 'N' # Not update
        elif vercmp_string(recipe_pv, recipe_result['version'], recipe_type) == 0:
            recipe_result['status'] = 'Y' # Up-to-date
        elif vercmp_string(recipe_pv, recipe_result['version'], recipe_type) == 1:
            recipe_result['status'] = 'D' # Downgrade, need to review why

        result_mutex.acquire()
        result[recipe] = recipe_result
        result_mutex.release()
