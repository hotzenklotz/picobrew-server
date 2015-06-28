#!/usr/bin/python2
# -*- coding: utf-8 -*-

import sys
from PyQt5.QtGui import * 
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

class RecipeAndStatus(QWidget):
    def __init__(self, parent=None, recipies=[]):
        super(RecipeAndStatus, self).__init__(parent)
        
        #ListView
        self.recipeList = QListView()
        self.recipeList.setUniformItemSizes(True)
        self.recipeList.setSelectionRectVisible(True)
        #ListModel
        self.recipeModel = QStandardItemModel(self.recipeList)
        for recipe in recipies:
            item = QStandardItem()
            item.setText(recipe)
            item.setEditable(False)
            item.setSizeHint(QSize(50,50))
            self.recipeModel.appendRow(item)
        self.recipeList.setModel(self.recipeModel)

        #Layout
        mainLayout = QGridLayout()
        self.updateButton = QPushButton("Update Recipes from Picobrew")

        mainLayout.addWidget(self.recipeList)
        mainLayout.addWidget(self.updateButton)
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
        self.splitter.setStyleSheet("Qsplitter{margin-top:20px;}")

        #Tabs for Possible Action Groups (i.e. brewing and Cleaning)
        self.tabWidget = QTabWidget()
        self.brewingRecipes = RecipeAndStatus(recipies=["Independence Pale Ale", "Eier Bräu"])

        self.tabWidget.addTab(self.brewingRecipes, "Brewing")
        self.cleaningRecipes = RecipeAndStatus(recipies=["Cleaning v1", "Rinse v1", "Pump"])
        self.tabWidget.addTab(self.cleaningRecipes, "Cleaning")
        #################split###################
        #Graphs
        self.graphs = QLabel("Graphs")
        self.graphs.setMinimumSize(200,200)
        self.graphs.setStyleSheet("QLabel {background-color : grey; color : white; }")

        #put both in split view
        self.splitter.addWidget(self.tabWidget)
        self.splitter.addWidget(self.graphs)
        self.setCentralWidget(self.splitter)

        #InfoLine
        self.statusBar().showMessage("Waiting for Picobrew to connect…")

    #MenuBarActions
    def openRecipes(self):
        fileDialog=QFileDialog( self )
        fileDialog.setWindowTitle("Choose Recipes from Disk" )
        fileDialog.setViewMode( QFileDialog.Detail )
        fileDialog.setNameFilters( [self.tr('Brew Files (*.brew)'), self.tr('Brew XML (*.xml)'), self.tr('All Files (*)')] )
        fileDialog.setDefaultSuffix( '.brew' )
        if fileDialog.exec_() :
            print fileDialog

if __name__ == '__main__':
    import sys
 
    app = QApplication(sys.argv)
    screen = Form()
    screen.show()
 
    sys.exit(app.exec_())