"""Supply-chain guard for .github/: every action is pinned to a full commit SHA,
every workflow sets top-level permissions, and Dependabot keeps the pins current."""
import glob
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GITHUB = os.path.join(ROOT, ".github")

USES = re.compile(r"""^\s*(?:-\s+)?uses:\s*["']?([^\s"'#]+)""")
FULL_SHA = re.compile(r"@[0-9a-f]{40}$")


def unpinned_uses(text):
    """Return every `uses:` ref that is not pinned to a 40-char commit SHA."""
    bad = []
    for line in text.replace("\r\n", "\n").split("\n"):
        m = USES.match(line)
        if not m:
            continue
        ref = m.group(1)
        if ref.startswith("./") or ref.startswith("docker://"):
            continue
        if not FULL_SHA.search(ref):
            bad.append(ref)
    return bad


def workflow_files():
    files = []
    for ext in ("yml", "yaml"):
        files += glob.glob(os.path.join(GITHUB, "workflows", "*." + ext))
        files += glob.glob(os.path.join(GITHUB, "actions", "**", "*." + ext), recursive=True)
    return sorted(files)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Parser(unittest.TestCase):
    def test_flags_tag_short_sha_and_branch(self):
        text = ("      - uses: actions/checkout@v4\n"
                "      - uses: actions/setup-python@a26af69\n"
                "        uses: 'owner/action@main'\n")
        self.assertEqual(unpinned_uses(text),
                         ["actions/checkout@v4", "actions/setup-python@a26af69", "owner/action@main"])

    def test_accepts_full_sha_local_and_docker(self):
        text = ("      - uses: actions/checkout@" + "a" * 40 + " # v4.4.0\n"
                "      - uses: ./.github/actions/local\n"
                "      - uses: docker://alpine:3.20\n")
        self.assertEqual(unpinned_uses(text), [])


class Workflows(unittest.TestCase):
    def test_has_workflows(self):
        self.assertTrue(workflow_files())

    def test_every_action_pinned_to_full_sha(self):
        for path in workflow_files():
            with self.subTest(path=os.path.relpath(path, ROOT)):
                self.assertEqual(unpinned_uses(read(path)), [])

    def test_every_workflow_sets_top_level_permissions(self):
        for path in glob.glob(os.path.join(GITHUB, "workflows", "*.y*ml")):
            with self.subTest(path=os.path.relpath(path, ROOT)):
                self.assertRegex(read(path), re.compile(r"^permissions:", re.M))

    def test_dependabot_watches_github_actions(self):
        text = read(os.path.join(GITHUB, "dependabot.yml"))
        self.assertRegex(text, r"""package-ecosystem:\s*["']?github-actions["']?""")


if __name__ == "__main__":
    unittest.main()
