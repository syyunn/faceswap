#!/usr/bin python3
""" Analysis tab of Display Frame of the Faceswap GUI """

import csv
import logging
import os
import tkinter as tk
from tkinter import ttk

from .display_graph import SessionGraph
from .display_page import DisplayPage
from .stats import Calculations, Session, SessionsTotals
from .tooltip import Tooltip
from .utils import FileHandler, get_config, get_images

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Analysis(DisplayPage):  # pylint: disable=too-many-ancestors
    """ Session analysis tab """
    def __init__(self, parent, tabname, helptext):
        logger.debug("Initializing: %s: (parent, %s, tabname: '%s', helptext: '%s')",
                     self.__class__.__name__, parent, tabname, helptext)
        super().__init__(parent, tabname, helptext)

        self.summary = None
        self.session = None
        self.add_options()
        self.add_main_frame()
        logger.debug("Initialized: %s", self.__class__.__name__)

    def set_vars(self):
        """ Analysis specific vars """
        selected_id = tk.StringVar()
        return {"selected_id": selected_id}

    def add_main_frame(self):
        """ Add the main frame to the subnotebook
            to hold stats and session data """
        logger.debug("Adding main frame")
        mainframe = self.subnotebook_add_page("stats")
        self.stats = StatsData(mainframe,
                               self.vars["selected_id"],
                               self.helptext["stats"])
        logger.debug("Added main frame")

    def add_options(self):
        """ Add the options bar """
        logger.debug("Adding options")
        self.reset_session_info()
        options = Options(self)
        options.add_options()
        logger.debug("Added options")

    def reset_session_info(self):
        """ Reset the session info status to default """
        logger.debug("Resetting session info")
        self.set_info("No session data loaded")

    def load_session(self):
        """ Load previously saved sessions """
        logger.debug("Loading session")
        self.clear_session()
        fullpath = FileHandler("filename", "state").retfile
        if not fullpath:
            return
        logger.debug("state_file: '%s'", fullpath)
        model_dir, state_file = os.path.split(fullpath)
        logger.debug("model_dir: '%s'", model_dir)
        model_name = self.get_model_name(model_dir, state_file)
        if not model_name:
            return
        self.session = Session(model_dir=model_dir, model_name=model_name)
        self.session.initialize_session(is_training=False)
        msg = os.path.split(state_file)[0]
        if len(msg) > 70:
            msg = "...{}".format(msg[-70:])
        self.set_session_summary(msg)

    @staticmethod
    def get_model_name(model_dir, state_file):
        """ Get the state file from the model directory """
        logger.debug("Getting model name")
        model_name = state_file.replace("_state.json", "")
        logger.debug("model_name: %s", model_name)
        logs_dir = os.path.join(model_dir, "{}_logs".format(model_name))
        if not os.path.isdir(logs_dir):
            logger.warning("No logs folder found in folder: '%s'", logs_dir)
            return None
        return model_name

    def reset_session(self):
        """ Reset currently training sessions """
        logger.debug("Reset current training session")
        self.clear_session()
        session = get_config().session
        if not session.initialized:
            logger.debug("Training not running")
            print("Training not running")
            return
        msg = "Currently running training session"
        self.session = session
        self.set_session_summary(msg)

    def set_session_summary(self, message):
        """ Set the summary data and info message """
        logger.debug("Setting session summary. (message: '%s')", message)
        self.summary = self.session.full_summary
        self.set_info("Session: {}".format(message))
        self.stats.tree_insert_data(self.summary)

    def clear_session(self):
        """ Clear sessions stats """
        logger.debug("Clearing session")
        self.summary = None
        self.stats.loaded_data = None
        self.stats.tree_clear()
        self.reset_session_info()

    def save_session(self):
        """ Save sessions stats to csv """
        logger.debug("Saving session")
        if not self.summary:
            logger.debug("No summary data loaded. Nothing to save")
            print("No summary data loaded. Nothing to save")
            return
        savefile = FileHandler("save", "csv").retfile
        if not savefile:
            logger.debug("No save file. Returning")
            return

        write_dicts = [val for val in self.summary.values()]
        fieldnames = sorted(key for key in write_dicts[0].keys())

        logger.debug("Saving to: '%s'", savefile)
        with savefile as outfile:
            csvout = csv.DictWriter(outfile, fieldnames)
            csvout.writeheader()
            for row in write_dicts:
                csvout.writerow(row)


class Options():
    """ Options bar of Analysis tab """
    def __init__(self, parent):
        logger.debug("Initializing: %s", self.__class__.__name__)
        self.optsframe = parent.optsframe
        self.parent = parent
        logger.debug("Initialized: %s", self.__class__.__name__)

    def add_options(self):
        """ Add the display tab options """
        self.add_buttons()

    def add_buttons(self):
        """ Add the option buttons """
        for btntype in ("reset", "clear", "save", "load"):
            logger.debug("Adding button: '%s'", btntype)
            cmd = getattr(self.parent, "{}_session".format(btntype))
            btn = ttk.Button(self.optsframe,
                             image=get_images().icons[btntype],
                             command=cmd)
            btn.pack(padx=2, side=tk.RIGHT)
            hlp = self.set_help(btntype)
            Tooltip(btn, text=hlp, wraplength=200)

    @staticmethod
    def set_help(btntype):
        """ Set the helptext for option buttons """
        logger.debug("Setting help")
        hlp = ""
        if btntype == "reset":
            hlp = "Load/Refresh stats for the currently training session"
        elif btntype == "clear":
            hlp = "Clear currently displayed session stats"
        elif btntype == "save":
            hlp = "Save session stats to csv"
        elif btntype == "load":
            hlp = "Load saved session stats"
        return hlp


class StatsData(ttk.Frame):  # pylint: disable=too-many-ancestors
    """ Stats frame of analysis tab """
    def __init__(self, parent, selected_id, helptext):
        logger.debug("Initializing: %s: (parent, %s, selected_id: %s, helptext: '%s')",
                     self.__class__.__name__, parent, selected_id, helptext)
        super().__init__(parent)
        self.pack(side=tk.TOP, padx=5, pady=5, expand=True, fill=tk.X, anchor=tk.N)

        self.loaded_data = None
        self.selected_id = selected_id
        self.popup_positions = list()

        self.add_label()
        self.tree = ttk.Treeview(self, height=1, selectmode=tk.BROWSE)
        self.scrollbar = ttk.Scrollbar(self,
                                       orient="vertical",
                                       command=self.tree.yview)
        self.columns = self.tree_configure(helptext)
        logger.debug("Initialized: %s", self.__class__.__name__)

    def add_label(self):
        """ Add Treeview Title """
        logger.debug("Adding Treeview title")
        lbl = ttk.Label(self, text="Session Stats", anchor=tk.CENTER)
        lbl.pack(side=tk.TOP, expand=True, fill=tk.X, padx=5, pady=5)

    def tree_configure(self, helptext):
        """ Build a treeview widget to hold the sessions stats """
        logger.debug("Configuring Treeview")
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        self.tree.tag_configure("total",
                                background="black",
                                foreground="white")
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<ButtonRelease-1>", self.select_item)
        Tooltip(self.tree, text=helptext, wraplength=200)
        return self.tree_columns()

    def tree_columns(self):
        """ Add the columns to the totals treeview """
        logger.debug("Adding Treeview columns")
        columns = (("session", 40, "#"),
                   ("start", 130, None),
                   ("end", 130, None),
                   ("elapsed", 90, None),
                   ("batch", 50, None),
                   ("iterations", 90, None),
                   ("rate", 60, "EGs/sec"))
        self.tree["columns"] = [column[0] for column in columns]

        for column in columns:
            text = column[2] if column[2] else column[0].title()
            logger.debug("Adding heading: '%s'", text)
            self.tree.heading(column[0], text=text)
            self.tree.column(column[0],
                             width=column[1],
                             anchor=tk.E,
                             minwidth=40)
        self.tree.column("#0", width=40)
        self.tree.heading("#0", text="Graphs")

        return [column[0] for column in columns]

    def tree_insert_data(self, sessions):
        """ Insert the data into the totals treeview """
        logger.debug("Inserting treeview data")
        self.tree.configure(height=len(sessions))

        for item in sessions:
            values = [item[column] for column in self.columns]
            kwargs = {"values": values, "image": get_images().icons["graph"]}
            if values[0] == "Total":
                kwargs["tags"] = "total"
            self.tree.insert("", "end", **kwargs)

    def tree_clear(self):
        """ Clear the totals tree """
        logger.debug("Clearing treeview data")
        self.tree.delete(* self.tree.get_children())
        self.tree.configure(height=1)

    def select_item(self, event):
        """ Update the session summary info with
            the selected item or launch graph """
        region = self.tree.identify("region", event.x, event.y)
        selection = self.tree.focus()
        values = self.tree.item(selection, "values")
        if values:
            logger.debug("Selected values: %s", values)
            self.selected_id.set(values[0])
            if region == "tree":
                self.data_popup()

    def data_popup(self):
        """ Pop up a window and control it's position """
        logger.debug("Popping up data window")
        scaling_factor = get_config().scaling_factor
        toplevel = SessionPopUp(self.loaded_data, self.selected_id.get())
        toplevel.title(self.data_popup_title())
        position = self.data_popup_get_position()
        height = int(720 * scaling_factor)
        width = int(400 * scaling_factor)
        toplevel.geometry("{}x{}+{}+{}".format(str(height),
                                               str(width),
                                               str(position[0]),
                                               str(position[1])))
        toplevel.update()

    def data_popup_title(self):
        """ Set the data popup title """
        logger.debug("Setting poup title")
        selected_id = self.selected_id.get()
        title = "All Sessions"
        if selected_id != "Total":
            title = "Session #{}".format(selected_id)
        logger.debug("Title: '%s'", title)
#        return "{} - {}".format(title, self.filename.get())

    def data_popup_get_position(self):
        """ Get the position of the next window """
        logger.debug("getting poup position")
        init_pos = [120, 120]
        pos = init_pos
        while True:
            if pos not in self.popup_positions:
                self.popup_positions.append(pos)
                break
            pos = [item + 200 for item in pos]
            init_pos, pos = self.data_popup_check_boundaries(init_pos, pos)
        logger.debug("Position: %s", pos)
        return pos

    def data_popup_check_boundaries(self, initial_position, position):
        """ Check that the popup remains within the screen boundaries """
        logger.debug("Checking poup boundaries: (initial_position: %s, position: %s)",
                     initial_position, position)
        boundary_x = self.winfo_screenwidth() - 120
        boundary_y = self.winfo_screenheight() - 120
        if position[0] >= boundary_x or position[1] >= boundary_y:
            initial_position = [initial_position[0] + 50, initial_position[1]]
            position = initial_position
        logger.debug("Returning poup boundaries: (initial_position: %s, position: %s)",
                     initial_position, position)
        return initial_position, position


class SessionPopUp(tk.Toplevel):
    """ Pop up for detailed graph/stats for selected session """
    def __init__(self, data, session_id):
        logger.debug("Initializing: %s: (data, %s, session_id: %s)",
                     self.__class__.__name__, data, session_id)
        super().__init__()

        self.is_totals = session_id == "Total"
        self.data = self.set_session_data(data, session_id)

        self.graph = None
        self.display_data = None

        self.vars = dict()
        self.graph_initialised = False
        self.build()
        logger.debug("Initialized: %s", self.__class__.__name__)

    def set_session_data(self, sessions, session_id):
        """ Set the correct list index based on the passed in session is """
        if self.is_totals:
            data = SessionsTotals(sessions).stats
        else:
            data = sessions[int(session_id) - 1]
        return data

    def build(self):
        """ Build the popup window """
        optsframe, graphframe = self.layout_frames()

        self.opts_build(optsframe)
        self.compile_display_data()
        self.graph_build(graphframe)

    def layout_frames(self):
        """ Top level container frames """
        leftframe = ttk.Frame(self)
        leftframe.pack(side=tk.LEFT, expand=False, fill=tk.BOTH, pady=5)

        sep = ttk.Frame(self, width=2, relief=tk.RIDGE)
        sep.pack(fill=tk.Y, side=tk.LEFT)

        rightframe = ttk.Frame(self)
        rightframe.pack(side=tk.RIGHT, fill=tk.BOTH, pady=5, expand=True)

        return leftframe, rightframe

    def opts_build(self, frame):
        """ Build Options into the options frame """
        self.opts_combobox(frame)
        self.opts_checkbuttons(frame)
        self.opts_entry(frame)
        self.opts_buttons(frame)
        sep = ttk.Frame(frame, height=2, relief=tk.RIDGE)
        sep.pack(fill=tk.X, pady=(5, 0), side=tk.BOTTOM)

    def opts_combobox(self, frame):
        """ Add the options combo boxes """
        choices = {"Display": ("Loss", "Rate"),
                   "Scale": ("Linear", "Log")}

        for item in ["Display", "Scale"]:
            var = tk.StringVar()
            cmd = self.optbtn_reset if item == "Display" else self.graph_scale
            var.trace("w", cmd)

            cmbframe = ttk.Frame(frame)
            cmbframe.pack(fill=tk.X, pady=5, padx=5, side=tk.TOP)
            lblcmb = ttk.Label(cmbframe,
                               text="{}:".format(item),
                               width=7,
                               anchor=tk.W)
            lblcmb.pack(padx=(0, 2), side=tk.LEFT)

            cmb = ttk.Combobox(cmbframe, textvariable=var, width=10)
            cmb["values"] = choices[item]
            cmb.current(0)
            cmb.pack(fill=tk.X, side=tk.RIGHT)

            self.vars[item.lower().strip()] = var

            hlp = self.set_help(item)
            Tooltip(cmbframe, text=hlp, wraplength=200)

    def opts_checkbuttons(self, frame):
        """ Add the options check buttons """
        for item in ("raw", "trend", "avg", "outliers"):
            if item == "avg":
                text = "Show Rolling Average"
            elif item == "outliers":
                text = "Flatten Outliers"
            else:
                text = "Show {}".format(item.title())
            var = tk.BooleanVar()

            if item == "raw":
                var.set(True)
            var.trace("w", self.optbtn_reset)
            self.vars[item] = var

            ctl = ttk.Checkbutton(frame, variable=var, text=text)
            ctl.pack(side=tk.TOP, padx=5, pady=5, anchor=tk.W)

            hlp = self.set_help(item)
            Tooltip(ctl, text=hlp, wraplength=200)

    def opts_entry(self, frame):
        """ Add the options entry boxes """
        for item in ("avgiterations", ):
            if item == "avgiterations":
                text = "Iterations to Average:"
                default = "10"

            entframe = ttk.Frame(frame)
            entframe.pack(fill=tk.X, pady=5, padx=5, side=tk.TOP)
            lbl = ttk.Label(entframe, text=text, anchor=tk.W)
            lbl.pack(padx=(0, 2), side=tk.LEFT)

            ctl = ttk.Entry(entframe, width=4, justify=tk.RIGHT)
            ctl.pack(side=tk.RIGHT, anchor=tk.W)
            ctl.insert(0, default)

            hlp = self.set_help(item)
            Tooltip(entframe, text=hlp, wraplength=200)

            self.vars[item] = ctl

    def opts_buttons(self, frame):
        """ Add the option buttons """
        btnframe = ttk.Frame(frame)
        btnframe.pack(fill=tk.X, pady=5, padx=5, side=tk.BOTTOM)

        for btntype in ("reset", "save"):
            cmd = getattr(self, "optbtn_{}".format(btntype))
            btn = ttk.Button(btnframe,
                             image=get_images().icons[btntype],
                             command=cmd)
            btn.pack(padx=2, side=tk.RIGHT)
            hlp = self.set_help(btntype)
            Tooltip(btn, text=hlp, wraplength=200)

    def optbtn_save(self):
        """ Action for save button press """
        savefile = FileHandler("save", "csv").retfile
        if not savefile:
            return

        save_data = self.display_data.stats
        fieldnames = sorted(key for key in save_data.keys())

        with savefile as outfile:
            csvout = csv.writer(outfile, delimiter=",")
            csvout.writerow(fieldnames)
            csvout.writerows(zip(*[save_data[key] for key in fieldnames]))

    def optbtn_reset(self, *args):  # pylint: disable=unused-argument
        """ Action for reset button press and checkbox changes"""
        if not self.graph_initialised:
            return
        self.compile_display_data()
        self.graph.refresh(self.display_data,
                           self.vars["display"].get(),
                           self.vars["scale"].get())

    def graph_scale(self, *args):  # pylint: disable=unused-argument
        """ Action for changing graph scale """
        if not self.graph_initialised:
            return
        self.graph.set_yscale_type(self.vars["scale"].get())

    @staticmethod
    def set_help(control):
        """ Set the helptext for option buttons """
        hlp = ""
        control = control.lower()
        if control == "reset":
            hlp = "Refresh graph"
        elif control == "save":
            hlp = "Save display data to csv"
        elif control == "avgiterations":
            hlp = "Number of data points to sample for rolling average"
        elif control == "outliers":
            hlp = "Flatten data points that fall more than 1 standard " \
                  "deviation from the mean to the mean value."
        elif control == "avg":
            hlp = "Display rolling average of the data"
        elif control == "raw":
            hlp = "Display raw data"
        elif control == "trend":
            hlp = "Display polynormal data trend"
        elif control == "display":
            hlp = "Set the data to display"
        elif control == "scale":
            hlp = "Change y-axis scale"
        return hlp

    def compile_display_data(self):
        """ Compile the data to be displayed """
        self.display_data = Calculations(self.data,
                                         self.vars["display"].get(),
                                         self.selections_to_list(),
                                         self.vars["avgiterations"].get(),
                                         self.vars["outliers"].get(),
                                         self.is_totals)

    def selections_to_list(self):
        """ Compile checkbox selections to list """
        selections = list()
        for key, val in self.vars.items():
            if (isinstance(val, tk.BooleanVar)
                    and key != "outliers"
                    and val.get()):
                selections.append(key)
        return selections

    def graph_build(self, frame):
        """ Build the graph in the top right paned window """
        self.graph = SessionGraph(frame,
                                  self.display_data,
                                  self.vars["display"].get(),
                                  self.vars["scale"].get())
        self.graph.pack(expand=True, fill=tk.BOTH)
        self.graph.build()
        self.graph_initialised = True
