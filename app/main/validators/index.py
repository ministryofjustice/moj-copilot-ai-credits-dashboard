import re

from flask import flash


def is_valid_email_pattern(email):
    pattern = "^[a-zA-Z0-9._-]+@{1}[a-zA-Z0-9.-]+$"
    regex = re.compile(pattern)
    result = regex.match(email)
    if result:
        return True
    return False


def check_for_empty_values(data):
    for key, value in data.items():
        if value == "" and key != 'ns_details':
            flash(f"Please enter a value for {key}.")
            return True
    return False


def validate_request(data):
    valid_business_areas = ['hmpps', 'hmcts', 'cjscp', 'other']
    valid_record_types = ['a', 'mx', 'cname', 'ns', 'other']
    if not is_valid_email_pattern(data['requestor_email']):
        flash("Please enter a valid email address.")
        return False
    if data['business_area'] not in valid_business_areas:
        flash("Please enter a valid business area name.")
        return False
    if data['record_type'] not in valid_record_types:
        flash("Please enter a valid DNS record type.")
        return False
    if check_for_empty_values(data):
        return False
    return True
