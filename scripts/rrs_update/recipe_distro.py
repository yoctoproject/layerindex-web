from rrs.models import RecipeDistro
from django.db import transaction

"""
    Update recipe distros entire table.
"""
def update_recipe_distros(envdata, layerbranch, pkglst_dir, logger):
    transaction.enter_transaction_management()
    transaction.managed(True)

    RecipeDistro.objects.filter(recipe__layerbranch = layerbranch).delete()

    for recipe, data in envdata.iteritems():
        distro_info = search_package_in_distros(pkglst_dir, recipe, data)
        for distro, alias in distro_info.iteritems():
            recipedistro = RecipeDistro()
            recipedistro.recipe = recipe
            recipedistro.distro = distro
            recipedistro.alias = alias
            recipedistro.save()

    transaction.commit()
    transaction.leave_transaction_management()

"""
    Searches the recipe's package in major distributions.
    Returns a dictionary containing pairs of (distro name, package aliases).
"""
def search_package_in_distros(pkglst_dir, recipe, data):
    distros = {}
    distro_aliases = {}

    recipe_name = recipe.pn

    recipe_name.replace("-native", "").replace("nativesdk-", "")
    recipe_name.replace("-cross", "").replace("-initial", "")

    distro_alias = data.getVar('DISTRO_PN_ALIAS', True)
    if distro_alias:
        # Gets info from DISTRO_PN_ALIAS into a dictionary containing 
        # the distribution as a key and the package name as value.
        for alias in distro_alias.split():
            if alias.find("=") != -1:
                (dist, pn_alias) = alias.split('=')
                distro_aliases[dist.strip().lower()] = pn_alias.strip()

    for distro_file in os.listdir(pkglst_dir):
        (distro, distro_release) = distro_file.split("-")

        if distro.lower() in distro_aliases:
            pn = distro_aliases[distro.lower()]
        else:
            pn = recipe_name

        f = open(os.path.join(pkglst_dir, distro_file), "rb")
        for line in f:
            (pkg, section) = line.split(":")
            if pn == pkg:
                distro_complete = distro + "-" + section[:-1]
                distros[distro_complete] = pn
                f.close()
                break
        f.close()

    return distros
