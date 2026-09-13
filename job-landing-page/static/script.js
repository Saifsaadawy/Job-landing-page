document.addEventListener("DOMContentLoaded", function () {
  var form = document.getElementById("settings-form");
  if (!form) return; // Not on the admin page.

  var saveBtn = document.getElementById("save-btn");
  var saveStatus = document.getElementById("save-status");
  var saveBtnDefaultHTML = saveBtn.innerHTML;

  function clearErrors() {
    form.querySelectorAll(".field.has-error").forEach(function (field) {
      field.classList.remove("has-error");
      var errorEl = field.querySelector(".field-error");
      if (errorEl) errorEl.textContent = "";
    });
  }

  function showFieldErrors(errors) {
    Object.keys(errors).forEach(function (fieldName) {
      var field = form.querySelector('[data-field="' + fieldName + '"]');
      if (!field) return;
      field.classList.add("has-error");
      var errorEl = field.querySelector(".field-error");
      if (errorEl) errorEl.textContent = errors[fieldName];
    });
  }

  function setStatus(message, type) {
    saveStatus.textContent = message;
    saveStatus.className = type || "";
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    clearErrors();
    setStatus("");

    var payload = {
      company_name: form.company_name.value.trim(),
      job_title: form.job_title.value.trim(),
      location: form.location.value.trim(),
      working_hours: form.working_hours.value.trim(),
      days_off: form.days_off.value.trim(),
      whatsapp_link: form.whatsapp_link.value.trim(),
      benefits: form.benefits.value,
      requirements: form.requirements.value,
    };

    saveBtn.disabled = true;
    saveBtn.innerHTML = "جارِ الحفظ<span class=\"spinner\"></span>";

    fetch(form.dataset.action || "/admin/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function (result) {
        if (result.ok && result.data.success) {
          setStatus("تم حفظ التعديلات بنجاح ✅", "success");
        } else {
          var errors = result.data.errors || {};
          showFieldErrors(errors);
          setStatus("فيه بيانات ناقصة أو غير صحيحة، راجع الحقول أعلاه ⚠️", "error");
        }
      })
      .catch(function () {
        setStatus("حصل خطأ أثناء الاتصال بالسيرفر، حاول تاني", "error");
      })
      .finally(function () {
        saveBtn.disabled = false;
        saveBtn.innerHTML = saveBtnDefaultHTML;
      });
  });
});
