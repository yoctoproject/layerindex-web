from django.db import transaction
from rrs.models import Maintainer, RecipeMaintainer

"""
    Update recipe maintainter if don't exist create new one.
"""
def update_recipe_maintainers(envdata, logger):
    transaction.enter_transaction_management()
    transaction.managed(True)

    for recipe, data in envdata.iteritems():
        maintainer = data.getVar('RECIPE_MAINTAINER', True) or ""

        if (maintainer == ""):
            m = Maintainer.objects.get(id = 0) # No Maintainer
        else:
            maintainer_name = " ".join(maintainer.split(' ')[0:-1])
            maintainer_email = maintainer.split(' ')[-1].replace('<', '').replace('>','')

            try:
                m = Maintainer.objects.get(name = maintainer_name)
                m.email = maintainer_email
            except Maintainer.DoesNotExist:
                m = Maintainer()
                m.name = maintainer_name
                m.email = maintainer_email

            m.save()

        try:
            rm = RecipeMaintainer.objects.get(recipe = recipe)
            rm.maintainer = m
        except RecipeMaintainer.DoesNotExist:
            rm = RecipeMaintainer()
            rm.recipe = recipe
            rm.maintainer = m

        rm.save()

    transaction.commit()
    transaction.leave_transaction_management()
