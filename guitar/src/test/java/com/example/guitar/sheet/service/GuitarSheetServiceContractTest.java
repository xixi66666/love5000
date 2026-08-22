package com.example.guitar.sheet.service;

import com.example.guitar.sheet.dto.SheetSaveRequest;
import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.vo.SheetDetailResponse;
import org.junit.jupiter.api.Test;
import org.springframework.web.multipart.MultipartFile;

import java.lang.reflect.Method;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class GuitarSheetServiceContractTest {

    @Test
    void publicMutationContractMatchesOwnerApiPlan() throws Exception {
        Method update = GuitarSheetService.class.getMethod("update", long.class, long.class, SheetSaveRequest.class);
        Method replace = GuitarSheetService.class.getMethod("replaceFiles", long.class, long.class, FileMode.class, List.class);
        Method delete = GuitarSheetService.class.getMethod("delete", long.class, long.class);

        assertThat(update.getReturnType()).isEqualTo(SheetDetailResponse.class);
        assertThat(replace.getReturnType()).isEqualTo(SheetDetailResponse.class);
        assertThat(delete.getReturnType()).isEqualTo(void.class);
    }
}
