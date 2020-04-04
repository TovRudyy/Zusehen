import concurrent.futures
import itertools
import logging
import os
import time

import numpy as np
import pandas as pd
from numba import jit

logging.basicConfig(format="%(levelname)s :: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


# import pyextrae.sequential as pyextrae

STATE_RECORD = "1"
EVENT_RECORD = "2"
COMM_RECORD = "3"

COL_STATE_RECORD = [
    "cpu_id",
    "appl_id",
    "task_id",
    "thread_id",
    "time_ini",
    "time_fi",
    "state",
]
COL_EVENT_RECORD = [
    "cpu_id",
    "appl_id",
    "task_id",
    "thread_id",
    "time",
    "event_t",
    "event_v",
]
COL_COMM_RECORD = [
    "cpu_send_id",
    "ptask_send_id",
    "task_send_id",
    "thread_send_id",
    "lsend",
    "psend",
    "cpu_recv_id",
    "ptask_recv_id",
    "task_recv_id",
    "thread_recv_id",
    "lrecv",
    "precv",
    "size",
    "tag",
]

MB = 1024 * 1024
GB = 1024 * 1024 * 1024
MAX_READ_BYTES = int(os.environ.get("STEPS", GB * 2))

# For pre-allocating memory
MIN_ELEM = int(os.environ.get("STEPS", 40000000))

STEPS = int(os.environ.get("STEPS", 200000))
RESIZE = 1


def get_state_row(line):
    # We discard the record type field
    return np.array([int(x) for x in line.split(":")])[1:]


def get_comm_row(line):
    # We discard the record type field
    return [int(x) for x in line.split(":")][1:]


def get_event_row(line):
    # We discard the record type field
    record = list(map(int, line.split(":")))[1:]
    # The same Event record line can contain more than 1 Event
    event_iter = iter(record[5:])
    return list(itertools.chain.from_iterable([record[:5] + [event, next(event_iter)] for event in event_iter]))


def isplit(iterable, part_size, group=list):
    """ Yields groups of length `part_size` of items found in iterator.
    group is a constructor which transforms an iterator into a object
    with `part_size` or less elements (example: list, tuple or set)
    """
    iterator = iter(iterable)
    while True:
        tmp = group(itertools.islice(iterator, 0, part_size))
        if not tmp:
            return
        yield tmp


def chunk_reader(filename, read_bytes):
    with open(filename, "r") as f:
        # Discard the header
        f.readline()
        while True:
            chunk = f.readlines(read_bytes)
            if not chunk:
                break
            yield chunk


def parse_records(chunk, arr_state, arr_event, arr_comm):
    stcount, evcount, commcount = 0, 0, 0
    # This is the padding between different records respectively
    stpadding, commpadding, evpadding = len(COL_STATE_RECORD), len(COL_COMM_RECORD), len(COL_EVENT_RECORD) * 10
    # The loop is divided in chunks of STEPS size
    for records in isplit(chunk, STEPS):
        for record in records:
            record_type = record[0]
            if record_type == STATE_RECORD:
                state = get_state_row(record)
                try:
                    arr_state[stcount : stcount + stpadding] = state
                except:
                    logger.warning("Catched exception: 'arr_state' need more space. Handling it...")
                    arr_state = np.concatenate((arr_state, np.zeros(STEPS * stpadding * RESIZE)))
                    arr_state[stcount : stcount + stpadding] = state
                stcount += stpadding
            elif record_type == EVENT_RECORD:
                # EVENT is a special type because we don't know how
                # long will be the returned list
                events = get_event_row(record)
                try:
                    arr_event[evcount : evcount + len(events)] = events
                except:
                    logger.warning("Catched exception: 'arr_event' need more space. Handling it...")
                    arr_event = np.concatenate((arr_event, np.zeros(STEPS * evpadding * RESIZE)))
                    arr_event[evcount : evcount + len(events)] = events
                evcount += len(events)
            elif record_type == COMM_RECORD:
                comm = get_comm_row(record)
                try:
                    arr_comm[commcount : commcount + commpadding] = comm
                except:
                    logger.warning("Catched exception: 'arr_comm' need more space. Handling it...")
                    arr_comm = np.concatenate((arr_comm, np.zeros(STEPS * commpadding * RESIZE)))
                    arr_comm[commcount : commcount + commpadding] = comm
                commcount += commpadding

        # Check if the arrays have enough free space for the next chunk iteration
        # If not, resize the arrays heuristically
        if (arr_state.size - stcount) < STEPS * stpadding:
            arr_state = np.concatenate((arr_state, np.zeros(STEPS * stpadding * RESIZE)))
        if (arr_event.size - evcount) < STEPS * evpadding:
            arr_event = np.concatenate((arr_event, np.zeros(STEPS * evpadding * RESIZE)))
        if (arr_comm.size - commcount) < STEPS * commpadding:
            arr_comm = np.concatenate((arr_comm, np.zeros(STEPS * commpadding * RESIZE)))

    return arr_state, stcount, arr_event, evcount, arr_comm, commcount


def seq_parser(chunks):
    start_time = time.time()
    # Pre-allocation of arrays
    arr_state = np.zeros(MIN_ELEM, dtype="int64")
    arr_event = np.zeros(MIN_ELEM, dtype="int64")
    arr_comm = np.zeros(MIN_ELEM, dtype="int64")
    
    arr_state, stcount, arr_event, evcount, arr_comm, commcount = parse_records(
        chunks, arr_state, arr_event, arr_comm
    )
    
    # logger.debug(f"TIMING (s) chunk_seq_parse:".ljust(30, " ") + "{:.3f}".format(time.time() - start_time))
    return arr_state, stcount, arr_event, evcount, arr_comm, commcount


THREADS = 4


def parallel_parse_as_dataframe(chunks, arr_state, stcount, arr_event, evcount, arr_comm, commcount):
    for par_chunk in isplit(chunk, STEPS / THREADS):
        with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
            size_chunk = len(par_chunk)
            for thread_id in range(1, THREADS + 1):
                st_boundary_start, st_boundary_end = (
                    stcount + size_chunk * thread_id,
                    stcount + size_chunk * (thread_id + 1),
                )
                arr_state, arr_event, arr_comm = executor.map(seq_parser,)

    return df_state, df_event, df_comm


def parse_as_dataframe(file):
    logger.debug(f"Using parameters: STEPS {STEPS}, MAX_READ_BYTES {MAX_READ_BYTES}, MIN_ELEM {MIN_ELEM}")
    start_time = time.time()
    # *count variables count how many elements we actually have
    arr_state, stcount, arr_event, evcount, arr_comm, commcount = np.array([], dtype="int64"), 0, np.array([], dtype="int64"), 0, np.array([], dtype="int64"), 0
    # This algorithm is a loop divided in chunks of MAX_READ_BYTES
    for chunk in chunk_reader(file, MAX_READ_BYTES):
        tmp_arr_state, tmp_stcount, tmp_arr_event, tmp_evcount, tmp_arr_comm, tmp_commcount = seq_parser(
            chunk)
        stcount, evcount, commcount = stcount+tmp_stcount, evcount+tmp_evcount, commcount+tmp_commcount
        # Join the temporal arrays with the main
        arr_state, arr_event, arr_comm = (
            np.concatenate((arr_state, tmp_arr_state[0:tmp_stcount])),
            np.concatenate((arr_event, tmp_arr_event[0:tmp_evcount])),
            np.concatenate((arr_comm, tmp_arr_comm[0:tmp_commcount])),
        )
        
        # Remove the positions that have not been used
        # arr_state, arr_event, arr_comm = arr_state[0:stcount], arr_event[0:evcount], arr_comm[0:commcount]
        
    logger.info(f"TIMING (s) el_time_parser:".ljust(30, " ") + "{:.3f}".format(time.time() - start_time))
    logger.info(
        f"ARRAY MAX SIZES (MB): {arr_state.nbytes//(1024*1024)} | { arr_event.nbytes//(1024*1024)} | {arr_comm.nbytes//(1024*1024)}"
    )

    # Reshape the arrays
    arr_state, arr_event, arr_comm = (
        arr_state.reshape((stcount // len(COL_STATE_RECORD), len(COL_STATE_RECORD))),
        arr_event.reshape((evcount // len(COL_EVENT_RECORD), len(COL_EVENT_RECORD))),
        arr_comm.reshape((commcount // len(COL_COMM_RECORD), len(COL_COMM_RECORD))),
    )

    df_state = pd.DataFrame(data=arr_state, columns=COL_STATE_RECORD)[COL_STATE_RECORD]
    df_event = pd.DataFrame(data=arr_event, columns=COL_EVENT_RECORD)[COL_EVENT_RECORD]
    df_comm = pd.DataFrame(data=arr_comm, columns=COL_COMM_RECORD)[COL_COMM_RECORD]

    return df_state, df_event, df_comm


def megadri_parallel_parse_as_dataframe(file):
    start_time = time.time()
    with ProcessPoolExecutor() as executor:
        parsed_file = executor.map(parse_lines_to_nparray, chunk_reader(file, MAX_READ_BYTES_PARALLEL))

    parsed_file = reduce(np.concatenate, parsed_file)

    df_state = parsed_file[0]
    df_event = parsed_file[1]
    df_comm = parsed_file[2]

    print(f"Total time: {time.time() - start_time}")
    return df_state, df_event, df_comm


TRACE = "/home/orudyy/Repositories/Zumsehen/test/test_files/traces/bt-mz.2x2.test.prv"
TRACE_HUGE = "/home/orudyy/apps/OpenFoam-Ashee/traces/rhoPimpleExtrae10TimeSteps.01.chop1.prv"
# TRACE = "/Users/adrianespejo/otros/Zusehen/traces/bt-mz.2x2-+A.x.prv"
# TRACE = "/home/orudyy/apps/OpenFoam-Ashee/traces/rhoPimpleExtrae40TimeSteps.prv"


def test():
    # TraceMetaData = parse_file(TRACE)
    df_state, df_event, df_comm = parse_as_dataframe(TRACE_HUGE)
    # df_state, df_event, df_comm = seq_parse_as_dataframe("/home/orudyy/Downloads/200MB.prv")
    # df_state, df_event, df_comm = seq_parse_as_dataframe("/home/orudyy/Downloads/200MB.prv")

    # pd.set_option("display.max_rows", None)
    print(f"\nResulting State records data:\n {df_state.shape}")
    print(f"\nResulting Event records data:\n {df_event.shape}")
    print(f"\nResulting Comm. records data:\n {df_comm.shape}")

    # input("Press any key to finish")
    # logging.info(f"Header State records data\n {df_state[-20:]}")

    # df_state2, df_event2, df_comm2 = load_as_dataframe(TRACE_HUGE)
    # print(df_comm == df_comm2)
    # print(df_state == df_state2)
    # print(df_event == df_event2)


if __name__ == "__main__":
    test()
