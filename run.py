import datetime

import gitlab

from confluence import ConfluencePage
from library import Library
from project import read_project_config
from functools import reduce

# TODO Check jira if version closed

CONFIG_FILE = "config.ini"


def main():
    timestamp = datetime.datetime.now().strftime("%c")
    print("Start:", timestamp)

    gl = gitlab.Gitlab.from_config(config_files=[CONFIG_FILE])

    # Init Library - get versions and make a pam from it
    library = Library(gl, CONFIG_FILE)

    # Read repos form config
    projects = read_project_config(CONFIG_FILE, gl)

    for project in projects:
        project.parse_revisions(library)

    # confluence = ConfluencePage(CONFIG_FILE, timestamp)
    # confluence.generate_page(library, projects)
    # confluence.publish_page()


def seconds_to_str(t):
    return "%d:%02d:%02d.%03d" % reduce(lambda ll, b: divmod(ll[0], b) + ll[1:], [(t * 1000, ), 1000, 60, 60])


if __name__ == '__main__':
    import time
    start_time = time.time()
    main()
    print("---Took %s seconds ---" % seconds_to_str(time.time() - start_time))
