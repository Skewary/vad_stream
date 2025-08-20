import ast
import matplotlib.pyplot as plt

def plot_from_results(path: str = 'results.txt', out: str = 'vad_compare.png'):
    with open(path, 'r') as f:
        lines = f.readlines()
    stream_raw = ast.literal_eval(lines[0].split(':',1)[1].strip())
    non_stream_raw = ast.literal_eval(lines[1].split(':',1)[1].strip())
    stream = [int(x) for x in stream_raw]
    non_stream = [1 if x else 0 for x in non_stream_raw]
    plt.figure(figsize=(8,3))
    plt.plot(stream, label='stream')
    plt.plot(non_stream, label='non-stream')
    plt.legend()
    plt.tight_layout()
    plt.savefig(out)

if __name__ == '__main__':
    plot_from_results()
