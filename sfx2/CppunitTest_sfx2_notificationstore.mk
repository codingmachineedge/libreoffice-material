# -*- Mode: makefile-gmake; tab-width: 4; indent-tabs-mode: t -*-
#
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

$(eval $(call gb_CppunitTest_CppunitTest,sfx2_notificationstore))

$(eval $(call gb_CppunitTest_add_exception_objects,sfx2_notificationstore, \
	sfx2/qa/cppunit/notificationcenterservice \
	sfx2/qa/cppunit/notificationstore \
	sfx2/qa/cppunit/notificationviewmodel \
))

$(eval $(call gb_CppunitTest_use_externals,sfx2_notificationstore, \
	boost_headers \
	zlib \
))

$(eval $(call gb_CppunitTest_use_libraries,sfx2_notificationstore, \
	comphelper \
	cppu \
	cppuhelper \
	sal \
	sfx \
	test \
	tl \
	utl \
))

$(eval $(call gb_CppunitTest_use_sdk_api,sfx2_notificationstore))

$(eval $(call gb_CppunitTest_use_ure,sfx2_notificationstore))
$(eval $(call gb_CppunitTest_use_vcl,sfx2_notificationstore))

$(eval $(call gb_CppunitTest_use_rdb,sfx2_notificationstore,services))

$(eval $(call gb_CppunitTest_use_configuration,sfx2_notificationstore))

# vim: set noet sw=4 ts=4:
