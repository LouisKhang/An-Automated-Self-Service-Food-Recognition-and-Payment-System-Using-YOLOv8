# main.py

from tkinter import Tk
from main_window import MainWindow

def main():
    """Khởi chạy ứng dụng"""
    root = Tk()
    app = MainWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()