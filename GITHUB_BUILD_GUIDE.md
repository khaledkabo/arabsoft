# ARAB SOFT - GitHub Windows Build

1. Create a GitHub repository.
2. Upload the contents of the `arab_work` folder (not the outer folder itself).
3. Open the repository -> Actions.
4. Select `Build ARAB SOFT for Windows`.
5. Click `Run workflow`.
6. When it finishes successfully, open the run and download `ARAB_SOFT_Service-Windows` from Artifacts.

The workflow uses GitHub's Windows runner and builds `ARAB_SOFT_Service.exe` with PyInstaller.
