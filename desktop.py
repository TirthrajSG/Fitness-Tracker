import webview

def main():
    # Create a native desktop window loading your chosen website
    window = webview.create_window(
        title="My Desktop App", 
        url="https://tirthrajsg.pythonanywhere.com",  # Replace with your website URL
        width=1024,
        height=768,
        resizable=True
    )
    
    # Start the GUI loop
    webview.start()

if __name__ == '__main__':
    main()
