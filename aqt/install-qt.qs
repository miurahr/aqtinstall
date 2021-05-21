function debugObject(object) {
    var lines = [];
    for (var i in object) {
        lines.push([i, object[i]].join(" "));
    }
    console.log(lines.join(","));
}

function Controller() {
    // Not empty dir is no problem.
    installer.setMessageBoxAutomaticAnswer("OverwriteTargetDirectory", QMessageBox.Yes);
    // If Qt is already installed in dir, acknowlegde the error but situation is stuck.
    installer.setMessageBoxAutomaticAnswer("TargetDirectoryInUse", QMessageBox.Ok);
    // Allow to quit the installer when listing packages.
    installer.setMessageBoxAutomaticAnswer("cancelInstallation", QMessageBox.Yes);
}

Controller.prototype.WelcomePageCallback = function() {
    console.log("Welcome Page");
    var widget = gui.currentPageWidget();
    widget.completeChanged.connect(function() {
        // For some reason, this page needs some delay.
        gui.clickButton(buttons.NextButton);
    });
}

Controller.prototype.CredentialsPageCallback = function() {
    console.log("Credentials Page");

	var login = installer.environmentVariable("QTLOGIN");
	var password = installer.environmentVariable("QTPASSWORD");

	if (login === "" || password === "") {
        gui.clickButton(buttons.NextButton);
	}

    var widget = gui.currentPageWidget();
	widget.loginWidget.EmailLineEdit.setText(login);
	widget.loginWidget.PasswordLineEdit.setText(password);
    gui.clickButton(buttons.NextButton);
}

Controller.prototype.IntroductionPageCallback = function() {
    console.log("Introduction Page");
    gui.clickButton(buttons.NextButton);
}

Controller.prototype.TargetDirectoryPageCallback = function() {
    console.log("Target Directory Page");
    var installDir = installer.environmentVariable("DESTDIR");
    if (installDir) {
        // If not present we assume we want to list packages.
        var widget = gui.currentPageWidget();
        widget.TargetDirectoryLineEdit.setText(installDir);
    }
    gui.clickButton(buttons.NextButton);
}

Controller.prototype.ComponentSelectionPageCallback = function() {
    console.log("Component Selection Page");

    var components = installer.components();
    console.log("Available packages: " + components.length);
    var packages = ["===LIST OF PACKAGES==="];
    for (var i = 0 ; i < components.length ;i++) {
        packages.push(components[i].name + "    " + components[i].displayName);
    }
    packages.push("===END OF PACKAGES===");
    console.log(packages.join("\n"));

    if (installer.environmentVariable("LIST_PACKAGE_ONLY")) {
        // Early exit
        gui.clickButton(buttons.CancelButton);
        return;
    }

    wantedPackages = installer.environmentVariable("PACKAGES").split(",");
    console.log("Trying to install ", wantedPackages);

    var widget = gui.currentPageWidget();
    widget.deselectAll();

    for (var i in wantedPackages) {
        name = wantedPackages[i];
        var found = false;
        for (var j in components) {
            if (components[j].name === name) {
                found = true;
                break;
            }
        }

        if (found) {
            console.log("Select " + name);
            widget.selectComponent(name);
        } else {
            console.log("Package " + name + " not found");
        }
    }
    widget.deselectComponent("qt.tools.qtcreator");
    widget.deselectComponent("qt.tools.doc");
    widget.deselectComponent("qt.tools.examples");

    gui.clickButton(buttons.NextButton);
}

Controller.prototype.LicenseAgreementPageCallback = function() {
    console.log("Accept License Agreement Page");
    var widget = gui.currentPageWidget();
    widget.AcceptLicenseRadioButton.setChecked(true);
    gui.clickButton(buttons.NextButton);
}

Controller.prototype.ReadyForInstallationPageCallback = function() {
    console.log("Ready For Installation Page");
    gui.clickButton(buttons.CommitButton);
}

Controller.prototype.PerformInstallationPageCallback = function() {
    console.log("Perform Installation Page");
    installer.installationFinished.connect(function() {
        console.log("Installation finished");
        gui.clickButton(buttons.NextButton);
    });
}

Controller.prototype.FinishedPageCallback = function() {
    console.log("Finished Page");
    var widget = gui.currentPageWidget();
    if (widget.LaunchQtCreatorCheckBoxForm) {
        widget.LaunchQtCreatorCheckBoxForm.launchQtCreatorCheckBox.setChecked(false);
    } else if (widget.RunItCheckBox) {
        widget.RunItCheckBox.setChecked(false);
    }
    gui.clickButton(buttons.FinishButton);
}
