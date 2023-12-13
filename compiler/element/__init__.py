import argparse
import os
import pathlib
import re
import sys
from pprint import pprint
from typing import Dict, List

from compiler import root_base_dir
from compiler.config import COMPILER_ROOT
from compiler.element.backend.finalizer import finalize
from compiler.element.backend.rustgen import RustContext, RustGenerator
from compiler.element.frontend import IRCompiler, Printer
from compiler.element.logger import ELEMENT_LOG as LOG
from compiler.element.optimize.consolidate import consolidate
from compiler.element.props.flow import FlowGraph, Property


def gen_code(
    engine_name: List[str],
    output_name: str,
    output_dir: str,
    backend_name: str,
    placement: str,
    verbose: bool = False,
) -> str:
    assert backend_name == "mrpc"
    compiler = IRCompiler()
    printer = Printer()
    generator = RustGenerator(placement)
    ctx = RustContext()

    irs = []

    for name in engine_name:
        with open(
            os.path.join(root_base_dir, f"examples/match_action/{name}.adn")
        ) as f:
            spec = f.read()
            ir = compiler.compile(spec)
            # p = ir.accept(printer, None)
            if verbose:
                print(p)

            irs.append(ir)

    consolidated = consolidate(irs)
    p = consolidated.accept(printer, None)
    if verbose:
        LOG.info("Consolidated IR:")
        print(p)

    finalize(output_name, ctx, output_dir, placement)


def compile_element_property(engine_name: List[str], verbose: bool = False) -> Dict:
    compiler = IRCompiler()
    printer = Printer()

    ret = (Property(), Property())
    stateful = False
    with open(
        os.path.join(root_base_dir, f"examples/match_action/{engine_name}.adn")
    ) as f:
        spec = f.read()
        ir = compiler.compile(spec)
        p = ir.accept(printer, None)
        if verbose:
            print(p)

        req = FlowGraph().analyze(ir.req, verbose)
        resp = FlowGraph().analyze(ir.resp, verbose)

        ret[0].block = ret[0].block or req.block
        ret[0].copy = ret[0].copy or req.copy
        ret[0].drop = ret[0].drop or req.drop
        ret[0].read = ret[0].read + req.read
        ret[0].write = ret[0].write + req.write
        ret[0].check()

        ret[1].block = ret[1].block or resp.block
        ret[1].copy = ret[1].copy or resp.copy
        ret[1].drop = ret[1].drop or resp.drop
        ret[1].read = ret[1].read + resp.read
        ret[1].write = ret[1].write + resp.write
        ret[1].check()

        stateful = stateful or len(ir.definition.internal) > 0
    return {
        "stateful": stateful,
        "request": {
            "read": ret[0].read,
            "write": ret[0].write,
            "drop": ret[0].drop,
            "block": ret[0].block,
            "copy": ret[0].copy,
        },
        "response": {
            "read": ret[1].read,
            "write": ret[1].write,
            "drop": ret[1].drop,
            "block": ret[1].block,
            "copy": ret[1].copy,
        },
    }
