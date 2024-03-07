from __future__ import annotations

from typing import Any, Dict, List, Union

from rich.panel import Panel

from compiler.element import compile_element_property
from compiler.graph.pseudo_element_compiler import pseudo_gen_property

global_element_id = 0


def fetch_global_id() -> str:
    """Assign a globally-unique id to the new element instance."""
    global global_element_id
    global_element_id += 1
    return global_element_id


class AbsElement:
    def __init__(
        self, info: Union[Dict[str, Any], str], partner: str = "", server: str = ""
    ):
        """
        Args:
            info(dict): basic element information, including name, config, proto, method, etc.
            partner(str): the name of its partner, used for optimization
        """
        if info == "NETWORK":
            self.name = info
            self.position = "N"
        else:
            self.id = fetch_global_id()
            self.name: List[str] = [info["name"]]
            self.path: List[str] = [info["path"]]
            self.server = (
                server  # the server side of the edge, used for finding adn spec
            )
            self.config = info["config"] if "config" in info else []
            self.position = info["position"] if "position" in info else "C/S"
            self.proto = info["proto"]
            self.method = info["method"]
            self.partner = partner

    @property
    def desc(self) -> str:
        return "_".join(self.name) + "_" + str(self.id)

    @property
    def deploy_name(self) -> str:
        return "".join([self.name[0].capitalize()] + self.name[1:])

    @property
    def lib_name(self) -> str:
        return self.server + "".join(self.name)[:24]

    @property
    def configs(self) -> str:
        return "\n".join(self.config)

    def __str__(self):
        return "+".join(self.name)

    def to_rich(self, position):
        color = "dark_green" if position == "client" else "blue"
        return Panel(
            self.deploy_name,
            style=color,
            expand=False,
        )

    def set_property_source(self, pseudo_property: bool):
        self.pseudo_property = pseudo_property

    @property
    def prop(self):
        if not hasattr(self, "_prop"):
            if self.name == "NETWORK":
                self._prop = {
                    "request": {
                        "delay": True,
                    },
                    "response": {
                        "delay": True,
                    },
                }
            else:
                assert hasattr(self, "pseudo_property"), "property source not set"
                if self.pseudo_property:
                    self._prop = pseudo_gen_property(self)
                else:
                    self._prop = compile_element_property(
                        self.name, self.path, server=self.server
                    )
                # TODO: remove this after property compiler has deduplication
                for path in ["request", "response"]:
                    for p in self._prop[path].keys():
                        if isinstance(self._prop[path][p], list):
                            self._prop[path][p] = list(set(self._prop[path][p]))
        return self._prop

    def has_prop(self, path: str, *props) -> bool:
        """Check whether the element has at least one of the listed properties.

        Args:
            path: "request" or "response"
            props: several property names

        Returns:
            at least one property exist => True
            all property not exist => False
        """
        assert path in ["request", "response"], f"path = {path} not exist"
        for p in props:
            if p in self.prop[path]:
                if isinstance(self.prop[path][p], list):
                    return True
                elif self.prop[path][p] is True:
                    return True
        return False

    def get_prop(self, path: str, p: str) -> Union[List[str], bool]:
        """Get property

        Args:
            path: "request" or "response"
            p: property name

        Returns:
        """
        assert path in ["request", "response"], f"path = {path} not exist"
        if p in self.prop[path]:
            return self.prop[path][p]
        else:
            return []

    def add_prop(self, path: str, p: str, contents: Union[str, List[str]]):
        """Add property

        Args:
            path: "request" or "response"
            p: property name
            contents: new contents to be added
        """
        assert path in ["request", "response"], f"path = {path} not exist"
        if p not in self.prop[path]:
            self.prop[path][p] = []
        if isinstance(contents, str):
            self.prop[path][p].append(contents)
        elif isinstance(contents, list):
            self.prop[path][p].extend(contents)
        else:
            raise ValueError

    def fuse(self, other: AbsElement):
        """Fuse another element in

        Args:
            other: the element to be fused.
        """
        self.name.extend(other.name)
        self.config.extend(other.config)
        self.position = (
            self.position
            if len(self.position) < len(other.position)
            else other.position
        )
        # Fuse properties
        # Consolidation is the last step of optimization. Therefore, only state
        # propertieds needs to be merged.
        self.prop["state"]["stateful"] |= other.prop["state"]["stateful"]
        if other.prop["state"]["consistency"] == "strong":
            self.prop["state"]["consistency"] = "strong"
