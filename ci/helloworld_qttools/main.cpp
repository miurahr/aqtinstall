#include <QtUiTools>
#include <QApplication>
#include <QPushButton>

int main(int argc, char **argv)
{
 QApplication app (argc, argv);
 QUiLoader loader;
 QPushButton button ("Hello world !");
 button.show();

 return app.exec();
}
