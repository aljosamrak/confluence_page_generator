import configparser
import re

from atlassian import Confluence


class ConfluencePage:

    dre = re.compile(r'(\d+)')

    def __init__(self, config_file, timestamp):
        self.timestamp = timestamp
        self.page = None

        config = configparser.ConfigParser()
        config.read(config_file)

        if "confluence" not in config.sections():
            print("No section 'confluence' found")
            exit(1)

        self.url = config.get("confluence", "url")
        self.username = config.get("confluence", "username")
        self.password = config.get("confluence", "password")
        self.page_id = config.get("confluence", "pageId")
        self.templateFile = config.get("confluence", "templateFile")
        title = config.get("confluence", "title")
        space = config.get("confluence", "space")

        if self.url is None or self.username is None or self.password is None:
            print("Config file missing configurations")
            exit(1)

        if self.page_id is None and (title is None or space is None):
            print("pageId or title and space missing")
            exit(1)

        self.confluence = Confluence(url=self.url, username=self.username, password=self.password)

        if self.page_id is None:
            if not self.confluence.page_exists(space, title):
                print(("Page Space: '%s' Title: '%s' does not exist" % (space, title)))
                exit(1)

            self.page_id = self.confluence.get_page_id(space, title)

    def generate_page(self, library, projects):
        # Generate page - latest version on develop
        project_versions_body = self.confluence_generate_last_versions(projects, library)

        # Generate page - which project depends on each library version
        lib_versions_body = self.confluence_generate_library_versions(library)

        template = open(self.templateFile, "r").read()
        self.page = template.format(timestamp=self.timestamp, lib_versions_body=lib_versions_body, app_versions_body=project_versions_body)

    def confluence_generate_last_versions(self, projects, library):
        app_versions_body = ""

        for project in projects:
            project_versions_sorted = sorted(project.versions,
                                             key=lambda version: [int(s) if s.isdigit() else s.lower() for s in
                                                                  re.split(self.dre, version.name)], reverse=True)
            if len(project_versions_sorted) <= 0:
                project_version = "Unknown"
                library_version = "Not using %s" % library.name
            else:
                latest_version = project_versions_sorted[0]
                project_version = latest_version.name
                library_version = latest_version.library_version if latest_version.library_version is not None else "Not using %s" % library.name

            app_versions_body += "<tr><td>{project_name}</td><td style=\"text-align: center;\"><strong>{project_version}</strong></td><td style=\"text-align: center;\"><strong>{library_version}</strong></td></tr>" \
                .format(project_name=project.name, project_version=project_version, library_version=library_version)

        return app_versions_body

    def confluence_generate_library_versions(self, library):
        sorted_versions = sorted(library.versions,
                                 key=lambda version: [int(s) if s.isdigit() else s.lower() for s in re.split(self.dre, version.name)],
                                 reverse=True)

        # TODO add links to release notes

        versions_body = ""
        for version in sorted_versions:
            if len(version.dependency_in) == 0:
                versions_body += "<tr><th><strong>{lib_name}</strong></th><td><strong>Not in use</strong></td><td></td></tr>\n" \
                    .format(lib_name=version.name)
            else:
                versions_body += "<tr><th rowspan=\"{num_of_dep}\"><strong>{lib_name}</strong></th><td>{dep_name}</td><td colspan=\"1\" style=\"text-align: center;\">{dep_rev}</td></tr>\n" \
                    .format(lib_name=version.name, num_of_dep=len(version.dependency_in), dep_name=version.dependency_in[0][0],
                            dep_rev=version.dependency_in[0][1].name)
                for dep in version.dependency_in[1:]:
                    versions_body += "<tr><td>{dep_name}</td><td colspan=\"1\" style=\"text-align: center;\">{dep_rev}</td></tr>" \
                        .format(dep_name=dep[0], dep_rev=dep[1].name)

        return versions_body

    def publish_page(self):
        if self.page is not None:
            print((self.confluence.update_page(self.page_id, "Test", self.page, type='page', representation='storage')))
