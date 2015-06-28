#!/usr/bin/python2
# -*- coding: utf-8 -*-

import sys
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

class RecipeAndStatus(QWidget):
    def __init__(self, parent=None, items=[]):
        super(RecipeAndStatus, self).__init__(parent)
        self.recipeView = QListView()
        
        #layout
        mainLayout = QGridLayout()
        mainLayout.addWidget(self.recipeView)
        self.setLayout(mainLayout)


class Form(QMainWindow):
    def __init__(self, parent=None):
        super(Form, self).__init__(parent)
        self.resize(800,600)

        #Menubar        
        menu = self.menuBar().addMenu('File')
        loadRecipesAction = menu.addAction('Recipes from Disk')
        loadRecipesAction.triggered.connect(self.openRecipes)

        #Widgets
        #SplitView of InfoGraphs and Recipes
        self.splitter = QSplitter(Qt.Vertical)

        #Tabs for Possible Action Groups (i.e. brewing and Cleaning)
        self.tabWidget = QTabWidget()
        self.brewingRecipes = RecipeAndStatus()
        self.tabWidget.addTab(self.brewingRecipes, "Brewing")
        self.cleaningRecipes = RecipeAndStatus()
        self.tabWidget.addTab(self.cleaningRecipes, "Cleaning")
        #################split###################
        #Graphs
        self.graphs = QLabel("Graphs")
        self.graphs.setStyleSheet("QLabel {background-color : grey; color : white; }")

        #put both in split view
        self.splitter.addWidget(self.tabWidget)
        self.splitter.addWidget(self.graphs)
        self.setCentralWidget(self.splitter)

        #InfoLine
        self.statusBar().showMessage("Waiting for Picobrew to connect…")

    #MenuBarActions
    def openRecipes(self): 
        pass


if __name__ == '__main__':
    import sys
 
    app = QApplication(sys.argv)
 
    screen = Form()
    screen.show()
 
    sys.exit(app.exec_())