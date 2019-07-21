import ConfigParser
import io

from gitlab.v4.objects import ProjectTag, ProjectBranch, GitlabGetError

from gitlab_utils import grep_from_file
from library import VersionType


def read_project_config(configuration_file, gitlab):
    # Read project config form config
    project_config = ProjectConfig(configuration_file)

    with open(configuration_file) as f:
        sample_config = f.read()
    config = ConfigParser.RawConfigParser(allow_no_value=True)
    config.readfp(io.BytesIO(sample_config))

    if "projectRepos" not in config.sections():
        print("No section 'projectRepos' found")
        exit(1)

    return map(lambda x: Project(x[0].title(), x[1], project_config, gitlab), config.items("projectRepos"))


class ProjectVersion:

    def __init__(self, name, revision, library_version):
        self.name = name
        self.library_version = library_version
        if isinstance(revision, ProjectBranch):
            self.type = VersionType.from_string(revision.name)
            self.from_ref = revision.name
        elif isinstance(revision, ProjectTag):
            self.type = VersionType.RELEASED
            self.from_ref = revision.name
        else:
            self.from_ref = str(revision)
            self.type = VersionType.from_string(self.from_ref)

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return self.name + " - " + self.from_ref


class ProjectConfig:

    def __init__(self, config_file):
        with open(config_file) as f:
            sample_config = f.read()
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.readfp(io.BytesIO(sample_config))

        if "project" not in config.sections():
            print("No section 'project' found")
            exit(1)

            list(filter(None, [x.strip() for x in config.get("project", "projectVersionPaths").splitlines()]))

        projectVersionPaths = list(filter(None, [x.strip() for x in config.get("project", "projectVersionPaths").splitlines()]))
        projectVersionRegex = list(filter(None, [x.strip() for x in config.get("project", "projectVersionRegex").splitlines()]))
        libraryVersionPath = list(filter(None, [x.strip() for x in config.get("project", "libraryVersionPath").splitlines()]))
        libraryVersionRegex = list(filter(None, [x.strip() for x in config.get("project", "libraryVersionRegex").splitlines()]))

        assert len(projectVersionPaths) == len(projectVersionRegex)
        assert len(libraryVersionPath) == len(libraryVersionRegex)

        self.project_version_paths = zip(projectVersionPaths, projectVersionRegex)
        self.lib_version_paths = zip(libraryVersionPath, libraryVersionRegex)

class Project:
    def __init__(self, name, repo, config, gitlab):
        self.name = name
        self.repo = repo
        self.config = config
        self.gitlab = gitlab
        self.versions = []

    def __hash__(self):
        return hash(self.repo)

    def __eq__(self, other):
        return self.repo == other.repo

    def __ne__(self, other):
        # Not strictly necessary, but to avoid having both x==y and x!=y
        # True at the same time
        return not (self == other)

    def parse_revisions(self, library):
        try:
            project = self.gitlab.projects.get(self.repo)
        except GitlabGetError:
            print "Project '%s' Not Found" % self.repo

        # Get all branches
        revisions = project.branches.list(all=True)

        # Checked for merged branches
        for revision in revisions:
            if revision.attributes["merged"]:
                print "=====ISSUE===== project: '%s' revision: '%s' has already been merged. It can be deleted" % (self.name, revision.name)

        # Check if more than 1 releases or hotfixes at once
        ready_to_release = filter(lambda x: any(map(lambda y: x.name.startswith(y), ["hotfix", "release"])), revisions)
        if len(ready_to_release) > 1:
            print "=====ISSUE===== project: '%s' has more that 1 ready to release branches %s" % (self.name,
                                                                          map(lambda x: x.name, ready_to_release))

        # Get only hotfix, release, develop and master branches and tags
        revisions = filter(lambda x: any(map(lambda y: x.name.startswith(y), ["hotfix", "release", "develop", "master"])), revisions)
        revisions.extend(project.tags.list(all=True))

        for revision in revisions:
            project_version = None
            library_version = None

            for project_version_conf in self.config.project_version_paths:
                project_version = grep_from_file(project, project_version_conf[0], revision.name, project_version_conf[1])
                if project_version is not None:
                    break
            for lib_version_conf in self.config.lib_version_paths:
                library_version = grep_from_file(project, lib_version_conf[0], revision.name, lib_version_conf[1])
                if library_version is not None:
                    break

            # If project users unknown version of the library raise issue
            if library_version is not None and library_version not in map(lambda x: x.name, library.versions):
                print "=====ISSUE===== repo: '%s' revision: '%s' uses unknown version of library: '%s'" % (self.repo, revision.name, library_version)

            # If tagged or ready to release version (hotfix/release/master) uses snapshot version of the library raise issue
            if library_version is not None and "SNAPSHOT" in library_version \
                    and (isinstance(revision, ProjectTag) or any(map(lambda y: revision.name.startswith(y), ["hotfix", "release", "master"]))):
                print "=====ISSUE===== repo: '%s' revision: '%s' uses SNAPSHOT versions on redy to release revision" % (self.repo, revision.name)

            if library_version is not None:
                for version in library.versions:
                    if version.name == library_version:
                        version.add_used_in_repo(self.repo, revision)

            if project_version is not None:
                self.versions.append(ProjectVersion(project_version, revision, library_version))
            # else:
            #     print "=====ISSUE===== repo: '%s' revision: '%s' unable to get version" % (self.repo, revision.name)
