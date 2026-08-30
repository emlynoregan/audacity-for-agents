/**********************************************************************

  Audacity: A Digital Audio Editor

  AudacityMessageBox.h

  Paul Licameli split this out of ErrorDialog.h

**********************************************************************/

#ifndef __AUDACITY_MESSAGE_BOX__
#define __AUDACITY_MESSAGE_BOX__

#include <wx/msgdlg.h>
#include "Internat.h"

extern WX_INIT_API TranslatableString AudacityMessageBoxCaptionStr();

// Do not use wxMessageBox!!  Its default window title does not translate!
WX_INIT_API int AudacityMessageBox(const TranslatableString& message,
   const TranslatableString& caption = XO("Message"),
   long style = wxOK | wxCENTRE,
   wxWindow *parent = NULL,
   int x = wxDefaultCoord, int y = wxDefaultCoord);

// Audacity for Agents: always on. This binary never shows windows or dialogs.
WX_INIT_API void SetAudacityBatchMode(bool enabled);
WX_INIT_API bool IsAudacityBatchMode();
// Print to stderr (parent console / redirected pipes). Never a dialog.
WX_INIT_API void AudacityBatchLog(const wxString& channel, const wxString& text);

#endif
