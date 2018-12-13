from datetime import datetime
from subprocess import call
import click
import os
import pandas as pd

CONFINR_PATH = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
METADATA_FILE = 'metadata.txt'
RUN_FOLDERS = ['OUTPUT', 'ANNOTATION']
SEQUENCE_COLUMNS = ['fw_seq', 'rvc_seq']


def load_input(input_path: str):
    """Load tab-delimited input data.

    Load tab-delimited data from input file and convert to DataFrame.
    Exclude columns where 'flagged' (column) is False. Extract sequences from selected columns.
    :param input_path: Path to input file.
    :return: DataFrame with forward- and reverse complement sequences.
    :raises KeyError: If requested key (e.g. sequence) is absent and can't be loaded.
    :raises FileNotFoundError: If file_path doesn't refer to an existing file.
    :raises ValueError: If an incorrect object type is used.
    """
    try:
        df = pd.read_table(input_path, sep='\t', header='infer', index_col=0, comment='#')
        return df[~df.flagged].loc[:, SEQUENCE_COLUMNS]
    except KeyError:
        raise KeyError
    except FileNotFoundError:
        raise FileNotFoundError
    except ValueError:
        raise ValueError


def convert_to_fasta(df: pd.DataFrame, output_path: str):
    """Convert tab-delimited data (.TSV) to FASTA format and write to a file.

    Include postfixes '/1' (forward sequences) and '/2' (reverse complement sequences) in FASTA header.
    Write formatted data to a file.
    :param df: DataFrame, should contain columns 'fw_seq' and 'rvc_seq' & headers as row indices to extract data from.
    :param output_path: Path to output file.
    :raises KeyError: If requested key (e.g. sequence) is absent and can't be loaded.
    :raises ValueError: If an incorrect object type is used.
    :raises FileExistsError: If output_path refers to an existing file.
    """
    if not os.path.exists(output_path):
        try:
            content = ''
            with open(output_path, 'w') as f:
                for index, row in df.iterrows():
                    if isinstance(row['fw_seq'], str):
                        content += '>' + index + ' /1\n' + row['fw_seq'] + '\n'
                    if isinstance(row['rvc_seq'], str):
                        content += '>' + index + ' /2\n' + row['rvc_seq'] + '\n'
                f.write(content)
        except KeyError:
            raise KeyError
        except ValueError:
            raise ValueError
    else:
        raise FileExistsError


@click.command()
@click.argument('i')
@click.option('--o', default='output.fasta', help='Path for output file')
def convert(i: str, o: str):
    """Convert tab-delimited data (in .TSV file) to FASTA format (in .FASTA file).

    :param i: Path to input file.
    :param o: Optional path for output file.
    """
    convert_to_fasta(load_input(i), o)


def initialize_run():
    """Initialize a ConFInR run by creating the required folder structure.

    Generate a run_id based on the date and time.
    Create defined run folders inside folder named after run_id.
    :raises OSError: If there is no such file or directory to create folders in.
    :return: Run folder name.
    """
    t = datetime.now()
    run_id = '_'.join(['RUN', '-'.join([str(t.day), str(t.month), str(t.year)]),
                       ''.join([str(t.hour) + 'h', str(t.minute) + 'm', str(t.second) + 's'])])
    run_id_folder = '/'.join((CONFINR_PATH, run_id))
    try:
        if not os.path.exists(run_id_folder):
            os.makedirs(run_id_folder)
            os.chdir(run_id_folder)
            for folder in RUN_FOLDERS:
                os.makedirs(folder)
            os.chdir('..')
        return run_id
    except OSError:
        raise OSError


def write_metadata(q=None, d=None, p=None, run_id=None):
    """Write metadata file for ConFInR run that includes query file, database and parameters.

    :param q: Path to query file.
    :param d: Path to DIAMOND database.
    :param p: Optional DIAMOND parameters.
    :param run_id: Run folder name.
    :raises OSError: If there is no such file or directory to create a file in.
    """
    try:
        with open('/'.join((CONFINR_PATH, run_id, METADATA_FILE)), 'a+') as f:
            if q is not None:
                f.write('Query file:\t' + q + '\n')
            if d is not None:
                if not os.path.exists(d):
                    d = '/'.join((CONFINR_PATH, 'REFERENCE', d))
                f.write('DIAMOND database:\t' + d + '\n')
            if p is not None:
                f.write('DIAMOND parameters:\t' + p.replace(' -', ', -') + '\n')
    except OSError:
        raise OSError


@click.command()
@click.argument('i')
@click.argument('d')
def make_diamond_db(i: str, d: str):
    """Run DIAMOND's makedb function in command line.

    Create DIAMOND command with input and database to be executed.
    Run DIAMOND command in shell.
    :param i: Path to input file.
    :param d: Path to DIAMOND database file.
    """
    command = 'diamond makedb --in ' + i + ' -d ' + '/'.join((CONFINR_PATH, 'REFERENCE', d))
    call(command, shell=True)


def run_diamond(d: str, q: str, run_id: str, params=None):
    """Run DIAMOND in BLASTX mode in command line.

    Resolve paths for output and database.
    Create DIAMOND command with database, query- and output file to be executed.
    Optionally, append parameters to command.
    Run DIAMOND command in shell.
    :param d: Path to DIAMOND database file.
    :param q: Path to query input file.
    :param run_id: Run folder name.
    :param params: Optional DIAMOND parameter(s), multiple should be surrounded with quotes.
    """
    o = '/'.join((CONFINR_PATH, run_id, 'OUTPUT/matches.m8'))
    if not os.path.exists(d):
        d = '/'.join((CONFINR_PATH, 'REFERENCE', d))
    command = 'diamond blastx -d ' + d + ' -q ' + q + ' -o ' + o
    if params is not None:
        command += ' '+params
    call(command, shell=True)


@click.command()
@click.argument('d')
@click.argument('q')
@click.option('--params', default=None, help='Optional DIAMOND parameters.')
def run_confinr(d: str, q: str, params: str):
    """Perform a ConFInR run; initialize run folder, run DIAMOND and write metadata file.

    :param d: Path to DIAMOND database file.
    :param q: Path to input query file.
    :param params: Optional DIAMOND parameter(s), multiple should be surrounded with quotes.
    """
    run_id = initialize_run()
    run_diamond(d, q, run_id, params)
    write_metadata(q=q, d=d, p=params, run_id=run_id)
    
