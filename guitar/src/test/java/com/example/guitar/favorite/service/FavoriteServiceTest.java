package com.example.guitar.favorite.service;

import com.example.guitar.favorite.dao.FavoriteDao;
import com.example.guitar.favorite.dto.FavoriteFolderRequest;
import com.example.guitar.favorite.model.FavoriteFolder;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DuplicateKeyException;

import java.util.Arrays;
import java.util.Collections;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class FavoriteServiceTest {

    private FavoriteDao favoriteDao;
    private FavoriteService service;

    @BeforeEach
    void setUp() {
        favoriteDao = mock(FavoriteDao.class);
        service = new FavoriteServiceImpl(favoriteDao);
    }

    @Test
    void createFolderTrimsNameAndUsesDefaultSortOrder() {
        when(favoriteDao.insertFolder(any(FavoriteFolder.class))).thenAnswer(invocation -> {
            FavoriteFolder folder = invocation.getArgument(0);
            folder.setId(11L);
            return 1;
        });
        when(favoriteDao.findOwnedFolder(11L, 7L)).thenAnswer(invocation -> {
            FavoriteFolder folder = new FavoriteFolder();
            folder.setId(11L);
            folder.setUserId(7L);
            folder.setName("练习");
            folder.setSortOrder(0);
            return folder;
        });

        service.createFolder(7L, request("  练习  ", null));

        ArgumentCaptor<FavoriteFolder> captor = ArgumentCaptor.forClass(FavoriteFolder.class);
        verify(favoriteDao).insertFolder(captor.capture());
        assertThat(captor.getValue().getUserId()).isEqualTo(7L);
        assertThat(captor.getValue().getName()).isEqualTo("练习");
        assertThat(captor.getValue().getSortOrder()).isZero();
    }

    @Test
    void folderNameMustContainOneToFiftyCharactersAfterTrim() {
        assertApiError(() -> service.createFolder(7L, request("   ", null)), "VALIDATION_ERROR");
        assertApiError(() -> service.createFolder(7L, request(repeat('a', 51), null)), "VALIDATION_ERROR");
        verifyNoInteractions(favoriteDao);
    }

    @Test
    void duplicateFolderNameMapsOnlyTheExpectedUniqueConstraint() {
        when(favoriteDao.insertFolder(any(FavoriteFolder.class)))
                .thenThrow(new DuplicateKeyException("uk_guitar_favorite_folder_name"));

        assertApiError(() -> service.createFolder(7L, request("练习", 2)), "FOLDER_NAME_EXISTS");

        DataIntegrityViolationException unrelated =
                new DataIntegrityViolationException("fk_guitar_favorite_folder_user");
        when(favoriteDao.insertFolder(any(FavoriteFolder.class))).thenThrow(unrelated);
        assertThatThrownBy(() -> service.createFolder(7L, request("练习", 2))).isSameAs(unrelated);
    }

    @Test
    void renameAndDeleteRequireAnOwnedFolderWithoutRevealingOtherOwners() {
        when(favoriteDao.findOwnedFolderForUpdate(9L, 7L)).thenReturn(null);

        assertApiError(() -> service.updateFolder(7L, 9L, request("新的名称", 3)), "FOLDER_NOT_FOUND");
        assertApiError(() -> service.deleteFolder(7L, 9L), "FOLDER_NOT_FOUND");

        verify(favoriteDao, never()).updateFolder(any(FavoriteFolder.class));
        verify(favoriteDao, never()).deleteFolder(9L, 7L);
    }

    @Test
    void sameSheetCanBeAddedToDifferentFoldersAndEachRelationIncrementsCounter() {
        when(favoriteDao.findOwnedFolderForUpdate(10L, 7L)).thenReturn(folder(10L, 7L, "A"));
        when(favoriteDao.findOwnedFolderForUpdate(20L, 7L)).thenReturn(folder(20L, 7L, "B"));
        when(favoriteDao.findPublishedSheetForUpdate(99L)).thenReturn(99L);
        when(favoriteDao.insertFavorite(7L, 10L, 99L)).thenReturn(1);
        when(favoriteDao.insertFavorite(7L, 20L, 99L)).thenReturn(1);
        when(favoriteDao.incrementFavoriteCount(99L)).thenReturn(1);

        service.addFavorite(7L, 10L, 99L);
        service.addFavorite(7L, 20L, 99L);

        verify(favoriteDao).insertFavorite(7L, 10L, 99L);
        verify(favoriteDao).insertFavorite(7L, 20L, 99L);
        verify(favoriteDao, org.mockito.Mockito.times(2)).incrementFavoriteCount(99L);
    }

    @Test
    void duplicateFavoriteMapsToStableErrorAndDoesNotIncrementCounter() {
        when(favoriteDao.findOwnedFolderForUpdate(10L, 7L)).thenReturn(folder(10L, 7L, "A"));
        when(favoriteDao.findPublishedSheetForUpdate(99L)).thenReturn(99L);
        when(favoriteDao.insertFavorite(7L, 10L, 99L))
                .thenThrow(new DuplicateKeyException("uk_guitar_favorite"));

        assertApiError(() -> service.addFavorite(7L, 10L, 99L), "FAVORITE_EXISTS");
        verify(favoriteDao, never()).incrementFavoriteCount(99L);
    }

    @Test
    void genericIntegrityFailureIsNotMisreportedAsDuplicateFavorite() {
        DataIntegrityViolationException unrelated = new DataIntegrityViolationException("connection lost");
        when(favoriteDao.findOwnedFolderForUpdate(10L, 7L)).thenReturn(folder(10L, 7L, "A"));
        when(favoriteDao.findPublishedSheetForUpdate(99L)).thenReturn(99L);
        when(favoriteDao.insertFavorite(7L, 10L, 99L)).thenThrow(unrelated);

        assertThatThrownBy(() -> service.addFavorite(7L, 10L, 99L)).isSameAs(unrelated);
    }

    @Test
    void offlineDeletedOrMissingSheetIsRejectedBeforeFavoriteInsert() {
        when(favoriteDao.findOwnedFolderForUpdate(10L, 7L)).thenReturn(folder(10L, 7L, "A"));
        when(favoriteDao.findPublishedSheetForUpdate(99L)).thenReturn(null);

        assertApiError(() -> service.addFavorite(7L, 10L, 99L), "SHEET_NOT_FOUND");
        verify(favoriteDao, never()).insertFavorite(7L, 10L, 99L);
    }

    @Test
    void addInsertsRelationBeforeIncrementingSheetCounter() {
        when(favoriteDao.findOwnedFolderForUpdate(10L, 7L)).thenReturn(folder(10L, 7L, "A"));
        when(favoriteDao.findPublishedSheetForUpdate(99L)).thenReturn(99L);
        when(favoriteDao.insertFavorite(7L, 10L, 99L)).thenReturn(1);
        when(favoriteDao.incrementFavoriteCount(99L)).thenReturn(1);

        service.addFavorite(7L, 10L, 99L);

        InOrder order = inOrder(favoriteDao);
        order.verify(favoriteDao).insertFavorite(7L, 10L, 99L);
        order.verify(favoriteDao).incrementFavoriteCount(99L);
    }

    @Test
    void removeDecrementsOnlyWhenARelationWasActuallyDeletedAndIsOtherwiseIdempotent() {
        when(favoriteDao.findOwnedFolderForUpdate(10L, 7L)).thenReturn(folder(10L, 7L, "A"));
        when(favoriteDao.deleteFavorite(7L, 10L, 99L)).thenReturn(1, 0);
        when(favoriteDao.decrementFavoriteCount(99L)).thenReturn(1);

        service.removeFavorite(7L, 10L, 99L);
        service.removeFavorite(7L, 10L, 99L);

        verify(favoriteDao, org.mockito.Mockito.times(2)).deleteFavorite(7L, 10L, 99L);
        verify(favoriteDao).decrementFavoriteCount(99L);
    }

    @Test
    void deletingNonEmptyFolderDeletesRelationsThenBatchDecrementsAndNeverDeletesSheets() {
        when(favoriteDao.findOwnedFolderForUpdate(10L, 7L)).thenReturn(folder(10L, 7L, "A"));
        when(favoriteDao.findSheetIdsByFolder(10L, 7L)).thenReturn(Arrays.asList(91L, 92L));
        when(favoriteDao.deleteFavoritesByFolder(10L, 7L)).thenReturn(2);
        when(favoriteDao.decrementFavoriteCounts(Arrays.asList(91L, 92L))).thenReturn(2);
        when(favoriteDao.deleteFolder(10L, 7L)).thenReturn(1);

        service.deleteFolder(7L, 10L);

        InOrder order = inOrder(favoriteDao);
        order.verify(favoriteDao).findSheetIdsByFolder(10L, 7L);
        order.verify(favoriteDao).deleteFavoritesByFolder(10L, 7L);
        order.verify(favoriteDao).decrementFavoriteCounts(Arrays.asList(91L, 92L));
        order.verify(favoriteDao).deleteFolder(10L, 7L);
    }

    @Test
    void listingFoldersAndSheetsAlwaysScopesQueriesToTheAuthenticatedOwner() {
        when(favoriteDao.findOwnedFolder(10L, 7L)).thenReturn(folder(10L, 7L, "A"));
        when(favoriteDao.findFoldersByUserId(7L)).thenReturn(Collections.singletonList(folder(10L, 7L, "A")));
        when(favoriteDao.findPublishedSheetsByFolder(10L, 7L)).thenReturn(Collections.emptyList());

        assertThat(service.listFolders(7L)).hasSize(1);
        assertThat(service.listSheets(7L, 10L)).isEmpty();

        verify(favoriteDao).findFoldersByUserId(7L);
        verify(favoriteDao).findPublishedSheetsByFolder(10L, 7L);
    }

    private FavoriteFolderRequest request(String name, Integer sortOrder) {
        FavoriteFolderRequest request = new FavoriteFolderRequest();
        request.setName(name);
        request.setSortOrder(sortOrder);
        return request;
    }

    private FavoriteFolder folder(long id, long userId, String name) {
        FavoriteFolder folder = new FavoriteFolder();
        folder.setId(id);
        folder.setUserId(userId);
        folder.setName(name);
        folder.setSortOrder(0);
        return folder;
    }

    private String repeat(char value, int length) {
        char[] chars = new char[length];
        Arrays.fill(chars, value);
        return new String(chars);
    }

    private void assertApiError(ThrowingCallable action, String code) {
        assertThatThrownBy(action::call).isInstanceOfSatisfying(GuitarApiException.class,
                exception -> assertThat(exception.getCode()).isEqualTo(code));
    }

    private interface ThrowingCallable {
        void call();
    }
}
