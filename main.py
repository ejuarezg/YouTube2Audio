import os
import shutil
import sys
import time
import requests
import qdarkstyle
from PyQt5.QtCore import QPersistentModelIndex, Qt, QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QImage, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QMainWindow,
    QTableWidgetItem,
)
import utils
from ui import UiMainWindow


BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_PATH = utils.get_download_path(BASE_PATH)
IMG_PATH = os.path.join(BASE_PATH, "img")
UTILS_PATH = os.path.join(BASE_PATH, "utils")


class MainPage(QMainWindow, UiMainWindow):
    """Main page of the application."""

    def __init__(self, parent=None):
        super(MainPage, self).__init__(parent)
        self.setupUi(self)
        # Hide the fetching, reattempt, error label, and revert button
        self.url_fetching_data_label.hide()
        self.url_error_label.hide()
        self.url_reattempt_load_label.hide()
        self.url_poor_connection.hide()
        self.revert_annotate.hide()
        # Activate hyperlink on upper right
        self.credit_url.linkActivated.connect(self.set_credit_url)
        self.credit_url.setText(
            '<a href="https://github.com/irahorecka/YouTube2Mp3">source code</a>'
        )
        # Connect the delete video button with the remove_selected_items fn.
        self.remove_from_table_button.clicked.connect(self.remove_selected_items)
        # Buttons connection with the appropriate functions
        self.save_as_mp4_box.setChecked(True)
        self.save_as_mp3_box.clicked.connect(self.set_check_mp3_box)
        self.save_as_mp4_box.clicked.connect(self.set_check_mp4_box)
        self.url_load_button.clicked.connect(self.url_loading_button_click)
        self.url_input.returnPressed.connect(self.url_load_button.click)
        self.url_input.mousePressEvent = lambda _: self.url_input.selectAll()
        self.download_button.clicked.connect(self.download_button_click)
        self.download_path.clicked.connect(self.get_download_path)
        self.itunes_annotate.clicked.connect(self.itunes_annotate_click)
        self.revert_annotate.clicked.connect(self.default_annotate_table)
        self.video_table.cellPressed.connect(self.load_table_content)
        # edit table cell with single click
        self.video_table.setEditTriggers(QAbstractItemView.CurrentChanged)
        # Input changes in video property text box to appropriate cell.
        self.change_video_info_input.clicked.connect(self.replace_cell_item)
        self.change_video_info_input_all.clicked.connect(self.replace_cell_column)
        self.video_info_input.returnPressed.connect(self.change_video_info_input.click)
        # Exit application
        self.cancel_button.clicked.connect(self.close)
        # Get download directory
        self.download_dir = DOWNLOAD_PATH
        self.download_folder_select.setText(
            self.get_parent_current_dir(self.download_dir)  # get directory tail
        )

    def url_loading_button_click(self):
        """Reads input data from self.url_input and creates an instance
        of the UrlLoading thread."""
        self.videos_dict = dict()  # Clear videos_dict upon reloading new playlist.
        playlist_url = self.get_cell_text(self.url_input)

        self.reflect_url_loading_status()
        self.url_fetching_data_label.show()
        self.calc = UrlLoading(playlist_url)
        self.calc.loadStatus.connect(self.reflect_url_loading_status)
        self.calc.countChanged.connect(self.url_loading_finished)
        self.calc.start()

    def reflect_url_loading_status(self, status=None):
        """Reflect YouTube url loading status. If no status is provided,
        hide all error label and keep table content."""
        self.video_table.clearContents()  # clear table content when loading
        self.video_info_input.setText("")  # clear video info input cell
        self.display_artwork(None)  # clear artwork display to default image
        self.url_poor_connection.hide()
        self.url_fetching_data_label.hide()
        self.url_reattempt_load_label.hide()
        self.url_error_label.hide()
        if status:
            if status == "success":
                return
            if status == "invalid url":
                self.url_error_label.show()
            elif status == "reattempt":
                self.url_reattempt_load_label.show()
            elif status == "server error":
                self.url_poor_connection.show()
            self.revert_annotate.hide()
            self.itunes_annotate.show()  # refresh Ask butler button

    def url_loading_finished(self, videos_dict, executed):
        """Retrieves data from thread when complete, updates GUI table."""
        # First entry of self.videos_dict in MainPage class
        self.videos_dict = videos_dict
        self.video_table.clearContents()  # clear table for new loaded content
        if executed:
            self.default_annotate_table()  # set table content
        else:
            self.url_error_label.show()

    def itunes_annotate_click(self):
        """Load iTunes annotation info on different thread."""
        self.video_info_input.setText("")
        try:
            assert self.videos_dict  # i.e. click annotate button with empty table
        except (AttributeError, AssertionError):
            self.video_info_input.setText("Could not get information.")
            return
        self.annotate = iTunesLoading(self.videos_dict)
        self.annotate.loadFinished.connect(self.itunes_annotate_finished)
        self.annotate.start()

    def itunes_annotate_finished(self, itunes_query_tuple, query_status):
        """Populate GUI table with iTunes meta information once
        iTunes annotation query complete."""
        for row_index, ITUNES_META_JSON in itunes_query_tuple:
            self.itunes_annotate_table(row_index, ITUNES_META_JSON)

        if not query_status:  # No iTunes metadata available or poor connection
            self.video_info_input.setText("Could not get information.")
        else:
            # show revert button if iTunes annotation loaded successfully
            self.itunes_annotate.hide()
            self.revert_annotate.show()

    def get_download_path(self):
        """Fetch download file path"""
        self.download_dir = QFileDialog.getExistingDirectory(
            self, "Open folder", DOWNLOAD_PATH
        )
        if not self.download_dir:
            self.download_dir = DOWNLOAD_PATH

        self.download_folder_select.setText(
            self.get_parent_current_dir(self.download_dir)
        )

    def download_button_click(self):
        """ Executes when the button is clicked """
        try:
            assert self.videos_dict  # assert self.videos_dict exists
        except (AttributeError, AssertionError):
            self.download_status.setText("No video to download.")
            return

        playlist_properties = self.get_playlist_properties()

        self.download_button.setEnabled(False)
        self.download_status.setText("Downloading...")
        self.down = DownloadingVideos(
            self.videos_dict,
            self.download_dir,
            playlist_properties,
            self.save_as_mp4_box.isChecked(),
        )
        self.down.downloadCount.connect(self.download_finished)
        self.down.start()

    def download_finished(self, download_time):
        """Emit changes to MainPage once dowload is complete."""
        _min = int(download_time // 60)
        sec = int(download_time % 60)
        self.download_status.setText(f"Download time: {_min} min. {sec} sec.")
        self.download_button.setEnabled(True)

    def default_annotate_table(self):
        """Default table annotation to video title in song columns"""
        if not self.videos_dict:  # i.e. an invalid playlist input
            self.video_table.clearContents()
            return

        self.video_info_input.setText("")

        for index, key in enumerate(self.videos_dict):
            self.video_table.setItem(index, 0, QTableWidgetItem(key))  # part of QWidget
            self.video_table.setItem(index, 1, QTableWidgetItem("Unknown"))
            self.video_table.setItem(index, 2, QTableWidgetItem("Unknown"))
            self.video_table.setItem(index, 3, QTableWidgetItem("Unknown"))
            self.video_table.setItem(index, 4, QTableWidgetItem("Unknown"))
        self.revert_annotate.hide()
        self.itunes_annotate.show()

    def itunes_annotate_table(self, row_index, ITUNES_META_JSON):
        """Provide iTunes annotation guess based on video title"""
        try:
            song_name, song_index = ITUNES_META_JSON["track_name"], 0
            album_name, album_index = ITUNES_META_JSON["album_name"], 1
            artist_name, artist_index = ITUNES_META_JSON["artist_name"], 2
            genre_name, genre_index = ITUNES_META_JSON["primary_genre_name"], 3
            artwork_name, artwork_index = ITUNES_META_JSON["artwork_url_fullres"], 4
        except TypeError:  # ITUNES_META_JSON was never called.
            song_name, song_index = (
                self.get_cell_text(self.video_table.item(row_index, 0)),
                0,
            )  # get video title
            if not song_name:
                song_name = "Unknown"

            album_name, album_index = "Unknown", 1
            artist_name, artist_index = "Unknown", 2
            genre_name, genre_index = "Unknown", 3
            artwork_name, artwork_index = "Unknown", 4

        self.video_table.setItem(row_index, song_index, QTableWidgetItem(song_name))
        self.video_table.setItem(row_index, album_index, QTableWidgetItem(album_name))
        self.video_table.setItem(row_index, artist_index, QTableWidgetItem(artist_name))
        self.video_table.setItem(row_index, genre_index, QTableWidgetItem(genre_name))
        self.video_table.setItem(
            row_index, artwork_index, QTableWidgetItem(artwork_name)
        )

    def load_table_content(self, row, column):
        """Display selected cell content into self.video_info_input
        and display selected artwork on Qpixmap widget."""
        # display video info in self.video_info_input
        self.display_video_info(row, column)

        # load and display video artwork
        artwork_file = self.get_cell_text(self.video_table.item(row, 4))
        self.loaded_artwork = ArtworkLoading(
            artwork_file
        )  # supposedly a url if populated
        self.loaded_artwork.loadFinished.connect(self.display_artwork)
        self.loaded_artwork.start()

    def display_video_info(self, row, column):
        """Display selected cell content in self.video_info_input"""
        self.video_info_input.setText(
            self.get_cell_text(self.video_table.item(row, column))
        )

    def display_artwork(self, artwork_content):
        """Display selected artwork on Qpixmap widget."""
        if not artwork_content:
            qt_artwork_content = os.path.join(IMG_PATH, "default_artwork.png")
            self.album_artwork.setPixmap(QPixmap(qt_artwork_content))
        else:
            qt_artwork_content = QImage()
            qt_artwork_content.loadFromData(artwork_content)
            self.album_artwork.setPixmap(QPixmap.fromImage(qt_artwork_content))

        self.album_artwork.setScaledContents(True)
        self.album_artwork.setAlignment(Qt.AlignCenter)

    def set_albm_artst_genr_artwrk(self, column_index):
        """Set cell content in song, album, artist, genre, or artwork
        column based on video info input or selected cell content."""
        rows = self.video_table.rowCount()
        for row_index in range(rows):
            item = self.video_table.item(row_index, column_index)  # get cell value
            if item and self.get_cell_text(item):
                self.video_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(self.get_cell_text(self.video_info_input)),
                )  # part of QWidget

    def replace_cell_item(self):
        """Change selected cell value to value in self.video_info_input."""
        row = self.video_table.currentIndex().row()
        column = self.video_table.currentIndex().column()
        video_info_input_value = self.get_cell_text(self.video_info_input)
        self.video_table.setItem(row, column, QTableWidgetItem(video_info_input_value))

    def replace_cell_column(self):
        """Change every occupied cell in the selected column to value
        in self.video_info_input."""
        column = self.video_table.currentIndex().column()
        self.set_albm_artst_genr_artwrk(column)

    def remove_selected_items(self):
        """Removes the selected items from self.videos_table and self.videos_dict.
        Table widget updates -- multiple row deletion capable."""
        try:
            video_list = [key_value for key_value in self.videos_dict.items()]
        except AttributeError:  # i.e. empty self.videos_dict
            video_list = []

        row_index_list = []
        for model_index in self.video_table.selectionModel().selectedRows():
            row = model_index.row()
            row_index = QPersistentModelIndex(model_index)
            row_index_list.append(row_index)
            try:
                current_key = video_list[row][0]
                del self.videos_dict[
                    current_key
                ]  # remove row item from self.videos_dict
            except (IndexError, KeyError):  # no item/key in video_list or videos_dict
                pass

        for index in row_index_list:
            self.video_table.removeRow(index.row())

    def get_playlist_properties(self):
        """Get video information from self.video_table to reflect to
        downloaded MP3 metadata."""
        playlist_properties = []

        for row_index, _ in enumerate(self.videos_dict.items()):
            song_properties = {}
            song_properties["song"] = self.get_cell_text(
                self.video_table.item(row_index, 0)
            ).replace(
                "/", "-"
            )  # will be filename -- change illegal char to legal - make func
            song_properties["album"] = self.get_cell_text(
                self.video_table.item(row_index, 1)
            )
            song_properties["artist"] = self.get_cell_text(
                self.video_table.item(row_index, 2)
            )
            song_properties["genre"] = self.get_cell_text(
                self.video_table.item(row_index, 3)
            )
            song_properties["artwork"] = self.get_cell_text(
                self.video_table.item(row_index, 4)
            )

            playlist_properties.append(
                song_properties
            )  # this assumes that dict will be ordered like list

        return playlist_properties

    def set_check_mp3_box(self):
        """if self.save_as_mp3_box is checked, uncheck
        self.save_as_mp4_box."""
        self.save_as_mp3_box.setChecked(True)
        self.save_as_mp4_box.setChecked(False)

    def set_check_mp4_box(self):
        """if self.save_as_mp4_box is checked, uncheck
        self.save_as_mp3_box."""
        self.save_as_mp3_box.setChecked(False)
        self.save_as_mp4_box.setChecked(True)

    @staticmethod
    def set_credit_url(url_str):
        """Set source code url on upper right of table."""
        QDesktopServices.openUrl(QUrl(url_str))

    @staticmethod
    def get_cell_text(cell_item):
        """Get text of cell value, if empty return empty str."""
        try:
            cell_item = cell_item.text()
            return cell_item
        except AttributeError:
            cell_item = ""
            return cell_item

    @staticmethod
    def get_parent_current_dir(current_path):
        """Get current and parent directory as str."""
        parent_dir, current_dir = os.path.split(current_path)
        parent_dir = os.path.split(parent_dir)[1]  # get tail of parent_dir
        return f"../{parent_dir}/{current_dir}"


class UrlLoading(QThread):
    """Load video data from YouTube url."""

    countChanged = pyqtSignal(dict, bool)
    loadStatus = pyqtSignal(str)

    def __init__(self, playlist_link, parent=None):
        QThread.__init__(self, parent)
        self.playlist_link = playlist_link
        self.reattempt_count = 0
        self.override_error = False

    def run(self):
        """Main function, gets all the playlist videos data, emits the info dict"""
        # allow 5 reattempts if error in fetching YouTube videos
        # else just get loaded videos by overriding error handling
        if self.reattempt_count > 5:
            self.override_error = True

        try:
            videos_dict = utils.get_youtube_content(
                self.playlist_link, self.override_error
            )
            if not videos_dict:
                # if empty videos_dict returns, throw invalid url warning.
                self.loadStatus.emit("invalid url")
            else:
                self.loadStatus.emit("success")
                self.countChanged.emit(videos_dict, True)

        except RuntimeError as error:  # handle error from video load fail
            error_message = str(error)
            if any(
                message in error_message
                for message in ["not a valid URL", "Unsupported URL", "list"]
            ):
                self.loadStatus.emit("invalid url")
            elif "nodename nor servname provided" in error_message:
                self.loadStatus.emit("server error")
            else:
                self.loadStatus.emit("reattempt")
                self.reattempt_count += 1
                self.run()


class iTunesLoading(QThread):
    """Get video data properties from iTunes."""

    loadFinished = pyqtSignal(tuple, bool)

    def __init__(self, videos_dict, parent=None):
        QThread.__init__(self, parent)
        self.videos_dict = videos_dict

    def run(self):
        """Multithread query to iTunes - return tuple."""
        try:
            query_iter = (
                (row_index, key_value)
                for row_index, key_value in enumerate(self.videos_dict.items())
            )
        except AttributeError:  # i.e. no content in table -- exit early
            return
        itunes_query = utils.map_threads(utils.thread_query_itunes, query_iter)
        itunes_query_tuple = tuple(itunes_query)
        if not self.check_itunes_nonetype(itunes_query_tuple):
            query_status = False
        else:
            query_status = True

        self.loadFinished.emit(itunes_query_tuple, query_status)

    @staticmethod
    def check_itunes_nonetype(query_tuple):
        """Check if none of the queries were successful."""
        _, itunes_query = tuple(zip(*query_tuple))
        try:
            # successful queries return a dict obj, which is unhashable
            set(itunes_query)
            return False
        except TypeError:
            return True


class ArtworkLoading(QThread):
    """Load artwork bytecode for display on GUI."""

    loadFinished = pyqtSignal(bytes)

    def __init__(self, artwork_url, parent=None):
        QThread.__init__(self, parent)
        self.artwork_url = artwork_url

    def run(self):
        artwork_img = bytes()
        # get url response - if not url, return empty bytes
        try:
            response = requests.get(self.artwork_url)
        except (requests.exceptions.MissingSchema, requests.exceptions.ConnectionError):
            self.loadFinished.emit(artwork_img)
            return

        # check validity of url response - if ok return img byte content
        if response.status_code != 200:  # invalid image url
            self.loadFinished.emit(artwork_img)
            return
        artwork_img = response.content
        self.loadFinished.emit(artwork_img)


class DownloadingVideos(QThread):
    """Download all videos from the videos_dict using the id."""

    downloadCount = pyqtSignal(float)  # attempt to emit delta_t

    def __init__(
        self, videos_dict, download_path, playlist_properties, save_as_mp4, parent=None
    ):
        QThread.__init__(self, parent)
        self.videos_dict = videos_dict
        self.download_path = download_path
        self.playlist_properties = playlist_properties
        self.save_as_mp4 = save_as_mp4

    def run(self):
        """ Main function, downloads videos by their id while emitting progress data"""
        # Download
        mp4_path = os.path.join(self.download_path, "mp4")
        try:
            os.mkdir(mp4_path)
        except FileExistsError:
            pass
        except FileNotFoundError:
            # If the user downloads to a folder, deletes the folder, and reattempts
            # to download to the same folder within the same session.
            raise RuntimeError(
                f'"{os.path.abspath(os.path.dirname(mp4_path))}" does not exist.\nEnsure this directory exists prior to executing download.'
            )

        time0 = time.time()
        video_properties = (
            (
                key_value,
                (self.download_path, mp4_path),
                self.playlist_properties[index],
                self.save_as_mp4,
            )
            for index, key_value in enumerate(
                self.videos_dict.items()
            )  # dict is naturally sorted in iteration
        )
        utils.map_threads(utils.thread_query_youtube, video_properties)
        shutil.rmtree(mp4_path)  # remove mp4 dir
        time1 = time.time()

        delta_t = time1 - time0
        self.downloadCount.emit(delta_t)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = MainPage()
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    widget.show()
    sys.exit(app.exec_())
