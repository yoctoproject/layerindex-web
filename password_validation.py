# SPDX-License-Identifier: MIT

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

import re

class ComplexityValidator(object):
    def validate(self, password, user=None):
        score = 0
        if re.search('[0-9]', password):
            score += 1
        if password.lower() != password:
            score += 1
        if re.search('[^a-zA-Z0-9]', password):
            score += 1

        if score < 2:
            raise ValidationError(
                _("This password does not contain at least two of: upper/lowercase characters; a number; a special (non-alphanumeric) character."),
                code='password_too_simple'
            )

    def get_help_text(self):
        return _(
            "Your password must contain at least two of: upper/lowercase characters; a number; a special (non-alphanumeric) character"
        )
