import ConfigParser
import io
import urllib2
from aetypes import Enum

import re
from gitlab.v4.objects import ProjectBranch, ProjectTag, GitlabGetError

from gitlab_utils import grep_from_file


class VersionType(Enum):
    UNKNOWN = None
    MASTER = 0
    DEVELOP = 1
    RELEASED = 2
    FEATURE = 3
    RELEASE = 4
    HOTFIX = 5
    SUPPORT = 6

    @classmethod
    def from_string(cls, name):
        if name == "develop":
            return cls.DEVELOP
        if name == "master":
            return cls.MASTER
        if name.startswith("feature/"):
            return cls.FEATURE
        if name.startswith("release/"):
            return cls.RELEASE
        if name.startswith("hotfix/"):
            return cls.HOTFIX
        if name.startswith("support/"):
            return cls.SUPPORT
        return cls.UNKNOWN


class LibraryVersion:

    def __init__(self, name, revision):
        self.name = name
        if isinstance(revision, ProjectBranch):
            self.type = VersionType.from_string(revision.name)
            self.from_ref = revision.name
        elif isinstance(revision, ProjectTag):
            self.type = VersionType.RELEASED
            self.from_ref = revision.name
        else:
            self.from_ref = str(revision)
            self.type = VersionType.from_string(self.from_ref)
        self.dependency_in = []

    def add_used_in_repo(self, repo, revision):
        self.dependency_in.append((repo, revision))

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return self.name + " - " + self.from_ref


class Library:

    def __init__(self, gitlab, configuration_file):
        self.name = "Name"
        self.repository = None
        self.version_file_path = None
        self.version_regex = None
        self.nexus_url = None
        self.nexus_regex = None

        self.read_config(configuration_file)

        self.project = gitlab.projects.get(self.repository)
        self.versions = None
        self.nexus_versions = []

        self.get_versions()

    def get_versions(self):
        if self.versions is not None:
            return self.versions

        self.nexus_versions = self.get_versions_from_nexus()

        versions = set()
        versions.update(
            map(lambda tag: LibraryVersion(tag.name, revision=tag), self.project.tags.list(all=True)))
        versions.update(
            map(lambda branch: LibraryVersion(self.get_version_for_revision(branch), revision=branch), self.project.branches.list(all=True)))

        versions.remove(LibraryVersion(None, revision=""))

        self.versions_sanity_check(versions)

        self.versions = versions
        return self.versions

    def get_version_for_revision(self, revision):
        if isinstance(revision, ProjectBranch):
            revision_name = revision.name
            if revision.attributes["merged"]:
                print "=====ISSUE===== %s revision: '%s' has already been merged. It can be deleted" % (self.name, revision_name)
        elif isinstance(revision, ProjectTag):
            revision_name = revision.name
        else:
            revision_name = str(revision)

        try:
            version = grep_from_file(self.project, self.version_file_path, revision_name, self.version_regex)
        except GitlabGetError:
            print "=====ISSUE===== %s revision: '%s' has no file: '%s'" % (self.name, revision.name, self.version_file_path)
            return None

        return version

    def get_versions_from_nexus(self):
        request = urllib2.Request(self.nexus_url)
        connection = urllib2.urlopen(request)
        content = connection.read()

        matches = re.findall(self.nexus_regex, content)
        if matches is not None:
            return matches

    def versions_sanity_check(self, versions):
        # Checked if released (on nexus) versions are tagged
        tagged_versions = map(lambda x: x.name, filter(lambda x: x.type == VersionType.RELEASED, versions))
        for version in set(self.nexus_versions) - set(tagged_versions):
            print "=====ISSUE===== %s artifact on nexus version: '%s' is not tagged" % (self.name, version)


        # TODO check on jira if version closed

        # Check if SNAPSHOOT on release nexus
        snapshot_versions = filter(lambda x: "SNAPSHOT" in x, self.nexus_versions)
        if len(snapshot_versions) > 0:
            print "=====ISSUE===== Snapshot version on release nexus: ", snapshot_versions

        # Check if version is on nexus
        for version in versions:
            if version.name in self.nexus_versions:
                if version.type is not VersionType.RELEASED:
                    print "=====ISSUE===== %s version: '%s' rev: '%s', must be tagged" % (self.name, version.name, version.from_ref)
            elif version.type is VersionType.RELEASED:
                print "=====ISSUE===== %s version: '%s' rev: '%s' is tagged but not on nexus" % (self.name, version.name, version.from_ref)

    def read_config(self, configuration_file):
        with open(configuration_file) as f:
            sample_config = f.read()
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.readfp(io.BytesIO(sample_config))

        if "library" not in config.sections():
            print("No section 'library' found")
            exit(1)

        self.name = config.get("library", "name")
        self.repository = config.get("library", "repo")
        self.version_file_path = config.get("library", "versionFilePath")
        self.version_regex = config.get("library", "versionRegex")
        self.nexus_url = config.get("library", "nexusLibraryUrl")
        self.nexus_regex = config.get("library", "nexusRegex")

        if self.repository is None or self.version_file_path is None or self.version_regex is None:
            print("Config file missing configurations")
            exit(1)
