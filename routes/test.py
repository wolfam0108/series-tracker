from flask import Blueprint, send_from_directory, current_app
import os

test_bp = Blueprint('test', __name__)

@test_bp.route('/directory-picker-test')
def directory_picker_test():
    return send_from_directory('static', 'directory_picker_test.html')