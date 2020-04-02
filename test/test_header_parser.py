import logging
from datetime import datetime

import pytest

from src.reader import paraver_header_parser

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def compare_trace_metadata(trace_a, trace_b):
    # For future usages
    if (
        trace_a.Name == trace_b.Name
        and trace_a.Path == trace_b.Path
        and trace_a.Type == trace_b.Type
        and trace_a.ExecTime == trace_b.ExecTime
        and trace_a.Date == trace_b.Date
        and trace_a.Nodes == trace_b.Nodes
        and trace_a.Apps == trace_b.Apps
    ):
        return True
    return False


# Python decorator
@pytest.mark.parametrize(
    "header,expected_header",
    (
        (
            "#Paraver (17/02/2020 at 11:37):1857922_ns:1(4):1:2(2:1,2:1)",
            (
                1857922,
                datetime.strptime("17/02/2020 11:37", "%d/%m/%Y %H:%M"),
                [4],
                [[{"nThreads": 2, "node": 1}, {"nThreads": 2, "node": 1}]],
            ),
        ),
        (
            "#Paraver (18/03/2020 at 11:15):1056311873701_ns:1(48):1:48(1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1,1:1),49",
            (
                1056311873701,
                datetime.strptime("18/03/2020 11:15", "%d/%m/%Y %H:%M"),
                [48],
                [
                    [
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                        {"nThreads": 1, "node": 1},
                    ]
                ],
            ),
        ),
        (
            "#Paraver (10/04/2001 at 18:21):620244_ns:0:1:1(4:0)",
            (620244, datetime.strptime("10/04/2001 18:21", "%d/%m/%Y %H:%M"), None, [[{"nThreads": 4, "node": 0}]]),
        ),
    ),
)
def test_header_parser(header, expected_header):
    assert expected_header == paraver_header_parser(header)