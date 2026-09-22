import subprocess

def get_sample_file(url):
    # check if file already exists before downloading
    subprocess.run(["wget", url])
    
if __name__ == "__main__":
    get_sample_file("https://download.blender.org/demo/cycles/loft.blend")
