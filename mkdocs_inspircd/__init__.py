"""
Preprocesses data files docs/*/modules/*.yml into markdown, so they can
be built by MkDocs like regular pages.
"""

import fnmatch
import functools
import glob
import pathlib
import os.path

import mkdocs.plugins
import mkdocs.structure.files
import jinja2
import yaml


@functools.lru_cache(10240)
def load_yaml(filename):
    with open(filename) as fd:
        return yaml.safe_load(fd)


def yml2md(filename, template):
    return template.render(load_yaml(filename))


class ExtendedFile(mkdocs.structure.files.File):
    """Like the original File class, but can also be a .yml module
    description."""

    def __init__(self, file, dest_dir, use_directory_urls):
        self.__dict__.update(file.__dict__)  # copy all attributes

        # Copy-pasted from mkdocs.structure.files.File's init;
        # but we need to run them again now that .yml are recognized
        # as documentation pages.
        self.dest_path = self._get_dest_path(use_directory_urls)
        self.abs_dest_path = os.path.normpath(os.path.join(dest_dir, self.dest_path))
        self.url = self._get_url(use_directory_urls)

    def is_documentation_page(self):
        return super().is_documentation_page() or self.is_inspircd_module_yaml()

    def is_inspircd_module_yaml(self):
        return fnmatch.fnmatch(self.src_path, "*/modules/*.yml")


class InspircdPlugin(mkdocs.plugins.BasePlugin):
    def __init__(self):
        super().__init__()
        self._modules = None
        self.env = jinja2.Environment(
            loader=jinja2.PackageLoader(__name__),
        )
        self.module_template = self.env.get_template("module.md.j2")

    def on_files(self, files, config):
        """Converts all original mkdocs.structure.files.File files to this
        plugin's ExtendedFile class, which behaves the same but accepts .yml
        files as input."""
        return mkdocs.structure.files.Files(
            [
                ExtendedFile(file, config["site_dir"], config["use_directory_urls"])
                for file in files
            ]
        )

    def on_page_read_source(self, page, config):
        """Replaces MkDocs's open() to read source files by reading the file
        directly and pre-rendering it to Markdown."""
        if page.file.is_inspircd_module_yaml():
            return yml2md(page.file.abs_src_path, template=self.module_template)

    def modules(self, config):
        if self._modules is None:
            self._modules = []
            for module_file in glob.glob(config["docs_dir"] + "/3/modules/*.yml"):
                self._modules.append(load_yaml(module_file))
        return self._modules

    def chmodes_table(self, config):
        modules = self.modules(config)
        template = self.env.get_template("mode_table.md.j2")
        return template.render(
            modes=[
                {**mode, "module": module["name"]}
                for module in modules
                if "chmodes" in module
                for mode in module["chmodes"]["chars"]
            ]
        )

    def umodes_table(self, config):
        modules = self.modules(config)
        template = self.env.get_template("mode_table.md.j2")
        return template.render(
            modes=[
                {**mode, "module": module["name"]}
                for module in modules
                if "umodes" in module
                for mode in module["umodes"]["chars"]
            ]
        )

    def extbans_table(self, config, type):
        modules = self.modules(config)
        template = self.env.get_template("extban_table.md.j2")
        return template.render(
            extbans=[
                {**extban, "module": module["name"]}
                for module in modules
                if "extbans" in module
                for extban in module["extbans"]["chars"]
                if extban["type"] == type
            ]
        )

    def snomasks_table(self, config):
        modules = self.modules(config)
        template = self.env.get_template("snomask_table.md.j2")
        return template.render(
            snomasks=[
                {**snomask, "module": module["name"]}
                for module in modules
                if "snomasks" in module
                for snomask in module["snomasks"]
            ]
        )

    def on_page_markdown(self, markdown, page, config, files):
        """Inserts dynamic/generated text in markdown pages."""
        return (
            markdown
            .replace("{{module_chmodes_table}}", self.chmodes_table(config))
            .replace("{{module_umodes_table}}", self.umodes_table(config))
            .replace("{{module_acting_extbans_table}}", self.extbans_table(config, "Acting"))
            .replace("{{module_matching_extbans_table}}", self.extbans_table(config, "Matching"))
            .replace("{{module_snomasks_table}}", self.snomasks_table(config))
        )
