/****************************************************************************
**
** Copyright (C) 2017 The Qt Company Ltd.
** Contact: https://www.qt.io/licensing/
**
** This file is part of the Qt Network Auth module of the Qt Toolkit.
**
** $QT_BEGIN_LICENSE:BSD$
** Commercial License Usage
** Licensees holding valid commercial Qt licenses may use this file in
** accordance with the commercial license agreement provided with the
** Software or, alternatively, in accordance with the terms contained in
** a written agreement between you and The Qt Company. For licensing terms
** and conditions see https://www.qt.io/terms-conditions. For further
** information use the contact form at https://www.qt.io/contact-us.
**
** BSD License Usage
** Alternatively, you may use this file under the terms of the BSD license
** as follows:
**
** "Redistribution and use in source and binary forms, with or without
** modification, are permitted provided that the following conditions are
** met:
**   * Redistributions of source code must retain the above copyright
**     notice, this list of conditions and the following disclaimer.
**   * Redistributions in binary form must reproduce the above copyright
**     notice, this list of conditions and the following disclaimer in
**     the documentation and/or other materials provided with the
**     distribution.
**   * Neither the name of The Qt Company Ltd nor the names of its
**     contributors may be used to endorse or promote products derived
**     from this software without specific prior written permission.
**
**
** THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
** "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
** LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
** A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
** OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
** SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
** LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
** DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
** THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
** (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
** OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
**
** $QT_END_LICENSE$
**
****************************************************************************/

#include "redditmodel.h"

#include <QtCore>
#include <QtNetwork>

RedditModel::RedditModel(QObject *parent) : QAbstractTableModel(parent) {}

RedditModel::RedditModel(const QString &clientId, QObject *parent) :
    QAbstractTableModel(parent),
    redditWrapper(clientId)
{
    grant();
}

int RedditModel::rowCount(const QModelIndex &parent) const
{
    Q_UNUSED(parent);
    return threads.size();
}

int RedditModel::columnCount(const QModelIndex &parent) const
{
    Q_UNUSED(parent);
    return threads.size() ? 1 : 0;
}

QVariant RedditModel::data(const QModelIndex &index, int role) const
{
    Q_UNUSED(role);
    if (!index.isValid())
        return QVariant();

    if (role == Qt::DisplayRole) {
        const auto childrenObject = threads.at(index.row());
        Q_ASSERT(childrenObject.value("data").isObject());
        const auto dataObject = childrenObject.value("data").toObject();
        return dataObject.value("title").toString();
    }
    return QVariant();
}

void RedditModel::grant()
{
    redditWrapper.grant();
    connect(&redditWrapper, &RedditWrapper::authenticated, this, &RedditModel::update);
}

void RedditModel::update()
{
    auto reply = redditWrapper.requestHotThreads();

    connect(reply, &QNetworkReply::finished, [=]() {
        reply->deleteLater();
        if (reply->error() != QNetworkReply::NoError) {
            emit error(reply->errorString());
            return;
        }
        const auto json = reply->readAll();
        const auto document = QJsonDocument::fromJson(json);
        Q_ASSERT(document.isObject());
        const auto rootObject = document.object();
        Q_ASSERT(rootObject.value("kind").toString() == "Listing");
        const auto dataValue = rootObject.value("data");
        Q_ASSERT(dataValue.isObject());
        const auto dataObject = dataValue.toObject();
        const auto childrenValue = dataObject.value("children");
        Q_ASSERT(childrenValue.isArray());
        const auto childrenArray = childrenValue.toArray();

        if (childrenArray.isEmpty())
            return;

        beginInsertRows(QModelIndex(), threads.size(), childrenArray.size() + threads.size() - 1);
        for (const auto childValue : qAsConst(childrenArray)) {
            Q_ASSERT(childValue.isObject());
            threads.append(childValue.toObject());
        }
        endInsertRows();
    });
}
